#!/usr/bin/env python3
"""
定时调度服务

使用 APScheduler 实现每日库存扫描等定时任务。
"""

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# 全局调度器实例
_scheduler: Optional[BackgroundScheduler] = None


def daily_inventory_scan_job():
    """
    每日库存扫描任务

    扫描所有待出清 SKU，生成折扣推荐，创建需要执行的任务，
    并发送飞书通知报告。
    """
    from app.services.sparql_service import SPARQLService
    from app.services.feishu_notification import get_feishu_service

    logger.info("[Scheduler] Starting daily inventory scan...")

    try:
        sparql = SPARQLService()
        feishu = get_feishu_service()

        # 1. 查询待出清 SKU
        skus = sparql.query_pending_clearance_skus()
        total_skus = len(skus)
        tasks_created = 0
        high_urgency_count = 0

        from datetime import date

        today = date.today()

        for row in skus:
            try:
                expiry_str = str(row.exp)
                expiry = date.fromisoformat(expiry_str)
                days_left = (expiry - today).days

                if days_left < 0:
                    continue

                # 高紧急判断（剩余 <= 1 天）
                if days_left <= 1:
                    high_urgency_count += 1

                # 查询折扣规则
                category_uri = str(row.cat)
                rules = sparql.query_clearance_rules(category_uri)

                # 匹配 tier
                tier_order = {
                    "UrgencyCritical": 0,
                    "UrgencyHigh": 1,
                    "UrgencyMedium": 2,
                    "UrgencyLow": 3,
                    "UrgencyPreventive": 4,
                }

                matched = None
                best_priority = 99

                for r in rules:
                    tier_min = int(r.tierMin)
                    tier_max = int(r.tierMax)
                    if tier_min <= days_left <= tier_max:
                        urgency_name = str(r.urgency).split("#")[-1]
                        priority = tier_order.get(urgency_name, 99)
                        if priority < best_priority:
                            matched = r
                            best_priority = priority

                if matched and days_left <= 1:
                    # 自动创建任务
                    task_id = f"T-{datetime.now().strftime('%Y%m%d')}-{tasks_created+1:04d}"
                    discount_rate = float(matched.recDiscount)

                    # 发送飞书通知
                    feishu.send_task_created_card(
                        task_id=task_id,
                        product_name=str(row.name),
                        category=str(row.catName),
                        discount_rate=discount_rate,
                        days_left=days_left,
                    )
                    tasks_created += 1

            except Exception as e:
                logger.warning(f"[Scheduler] Error processing SKU {row.sku}: {e}")
                continue

        # 发送每日报告
        if total_skus > 0:
            feishu.send_daily_scan_report(
                total_skus=total_skus,
                tasks_created=tasks_created,
                high_urgency_count=high_urgency_count,
            )

        logger.info(
            f"[Scheduler] Daily scan complete: {total_skus} SKUs scanned, "
            f"{tasks_created} tasks created, {high_urgency_count} high urgency"
        )

    except Exception as e:
        logger.error(f"[Scheduler] Daily scan failed: {e}")


def init_scheduler() -> BackgroundScheduler:
    """初始化并启动调度器"""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.info("[Scheduler] Scheduler already running")
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # 每日早上 8:00 执行库存扫描
    _scheduler.add_job(
        daily_inventory_scan_job,
        trigger=CronTrigger(hour=8, minute=0, timezone="Asia/Shanghai"),
        id="daily_inventory_scan",
        name="每日库存扫描",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("[Scheduler] Scheduler started with daily scan at 08:00")
    return _scheduler


def get_scheduler() -> Optional[BackgroundScheduler]:
    """获取调度器实例（需先调用 init_scheduler）"""
    return _scheduler


def shutdown_scheduler():
    """关闭调度器"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[Scheduler] Scheduler shutdown")


def trigger_inventory_scan_now():
    """手动触发立即库存扫描（用于测试）"""
    daily_inventory_scan_job()