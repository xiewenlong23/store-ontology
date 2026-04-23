#!/usr/bin/env python3
"""
POS 模拟器 - POS 数据闭环

模拟 POS 系统定期回写销售数据，计算 sell_through_rate，
触发任务复核流程。
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.services.event_system import EventType, get_event_bus

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
POS_SALES_FILE = DATA_DIR / "pos_sales.json"


def load_pos_sales() -> list[dict]:
    """加载POS销售记录（读锁）"""
    if not POS_SALES_FILE.exists():
        return []
    with open(POS_SALES_FILE) as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def save_pos_sales(sales: list[dict]) -> None:
    """保存POS销售记录（写锁）"""
    POS_SALES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POS_SALES_FILE, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(sales, f, indent=2, default=str)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class POSSimulator:
    """
    POS 模拟器

    模拟真实POS系统，定期扫描待出清任务，
    随机生成销售数据，回写 sell_through_rate。
    """

    def __init__(self) -> None:
        self._event_bus = get_event_bus()

    def record_sale(
        self,
        task_id: str,
        product_id: str,
        original_stock: int,
        discount_rate: float,
        days_elapsed: int = 1,
    ) -> dict:
        """
        模拟一次POS销售记录

        Args:
            task_id: 任务ID
            product_id: 商品ID
            original_stock: 原始库存
            discount_rate: 折扣率
            days_elapsed: 经过的天数

        Returns:
            销售记录dict
        """
        # 模拟销售模式：
        # - 高折扣 + 短保质期 → 高售罄率
        # - 低折扣 + 长保质期 → 低售罄率
        base_sell_rate = discount_rate * 0.8  # 基础售罄率与折扣正相关

        # 保质期越短，售罄越快
        if days_elapsed <= 1:
            multiplier = 1.2
        elif days_elapsed <= 3:
            multiplier = 1.0
        else:
            multiplier = 0.7

        sell_rate = min(base_sell_rate * multiplier * random.uniform(0.8, 1.2), 1.0)
        sold_qty = int(original_stock * sell_rate)
        remaining = original_stock - sold_qty

        # 库存消耗（模拟商品被买走）
        self._update_product_inventory(product_id, remaining)

        record = {
            "record_id": f"POS-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}",
            "task_id": task_id,
            "product_id": product_id,
            "sold_qty": sold_qty,
            "remaining_stock": remaining,
            "original_stock": original_stock,
            "sell_through_rate": round(sold_qty / original_stock, 4) if original_stock > 0 else 0.0,
            "discount_rate": discount_rate,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        # 保存到POS销售记录
        sales = load_pos_sales()
        sales.append(record)
        save_pos_sales(sales)

        # 发送POS销售事件
        self._event_bus.emit_pos_sale_event(
            task_id=task_id,
            product_id=product_id,
            sold_qty=sold_qty,
            sell_through_rate=record["sell_through_rate"],
        )

        logger.info(
            f"[POS] Sale recorded: task={task_id}, sold={sold_qty}/{original_stock}, "
            f"rate={record['sell_through_rate']:.2%}"
        )

        return record

    def _update_product_inventory(self, product_id: str, remaining: int) -> None:
        """更新商品库存（模拟POS系统更新库存，写锁）"""
        from app.routers.tasks import DATA_DIR

        tasks_file = DATA_DIR / "tasks.json"
        if tasks_file.exists():
            with open(tasks_file) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    tasks = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            for t in tasks:
                if t.get("product_id") == product_id and t.get("original_stock", 0) == remaining + 1:
                    t["original_stock"] = remaining  # 模拟库存变化
                    break
            with open(tasks_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(tasks, f, indent=2, default=str)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def simulate_daily_sales(
        self,
        task_id: str,
        product_id: str,
        original_stock: int,
        discount_rate: float,
        days_elapsed: int,
    ) -> dict:
        """
        模拟每日POS销售（用于批量处理）

        每天的销售量按固定比例递减（现实模型）
        """
        daily_sales = []
        current_stock = original_stock

        for day in range(1, days_elapsed + 1):
            if current_stock <= 0:
                break

            # 每天销售量 = 当前库存 * 日均售罄率
            daily_rate = discount_rate * (1 - (day - 1) * 0.1) * random.uniform(0.7, 1.0)
            daily_rate = max(min(daily_rate, 1.0), 0.0)
            sold = int(current_stock * daily_rate)
            sold = min(sold, current_stock)

            current_stock -= sold

            record = {
                "record_id": f"POS-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{day:02d}-{product_id}",
                "task_id": task_id,
                "product_id": product_id,
                "sold_qty": sold,
                "remaining_stock": current_stock,
                "original_stock": original_stock,
                "sell_through_rate": round((original_stock - current_stock) / original_stock, 4) if original_stock > 0 else 0.0,
                "discount_rate": discount_rate,
                "day": day,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            daily_sales.append(record)

            # 发送每日销售事件
            self._event_bus.emit_pos_sale_event(
                task_id=task_id,
                product_id=product_id,
                sold_qty=sold,
                sell_through_rate=record["sell_through_rate"],
            )

        # 汇总保存
        if daily_sales:
            sales = load_pos_sales()
            sales.extend(daily_sales)
            save_pos_sales(sales)

        final_rate = (original_stock - current_stock) / original_stock if original_stock > 0 else 0.0
        logger.info(
            f"[POS] Daily sales simulated for {task_id}: "
            f"{original_stock - current_stock}/{original_stock}, final_rate={final_rate:.2%}"
        )

        return {
            "task_id": task_id,
            "product_id": product_id,
            "total_sold": original_stock - current_stock,
            "final_stock": current_stock,
            "sell_through_rate": round(final_rate, 4),
            "days_simulated": min(days_elapsed, len(daily_sales)),
            "daily_records": daily_sales,
        }


_pos_simulator: Optional[POSSimulator] = None


def get_pos_simulator() -> POSSimulator:
    """获取POS模拟器单例"""
    global _pos_simulator
    if _pos_simulator is None:
        _pos_simulator = POSSimulator()
    return _pos_simulator
