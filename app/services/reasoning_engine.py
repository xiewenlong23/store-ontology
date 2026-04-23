#!/usr/bin/env python3
"""
Fast Path 规则引擎 — 毫秒级确定性推理

适用场景：
- 临期商品 → 查询 <3天 → 直接执行打折
- 确定性业务规则，毫秒级响应

架构位置：Layer 3 三级推理引擎的第一层
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

from app.services.discount_constants import DISCOUNT_TIERS, get_fallback_tier
from app.services.inventory_service import check_product_exemption_from_json

logger = logging.getLogger(__name__)


class ReasoningPath(str, Enum):
    """推理路径枚举"""
    FAST = "Fast Path (规则引擎)"
    MEDIUM = "Medium Path (OWL 推理)"
    SLOW = "Slow Path (LLM Agent)"


class Action(str, Enum):
    """操作动作枚举"""
    APPLY_DISCOUNT = "APPLY_DISCOUNT"
    NO_ACTION = "NO_ACTION"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    EXEMPTED = "EXEMPTED"


# 豁免品类（不参与临期打折）
EXEMPT_CATEGORIES: set[str] = set()

# 库存调整阈值
HIGH_STOCK_THRESHOLD = 100
STOCK_ADJUSTMENT_RATE = 0.8
MAX_AGGRESSIVE_DISCOUNT = 0.30

# 紧急临期阈值（天数）
CRITICAL_DAYS = 1
HIGH_URGENCY_DAYS = 2


@dataclass
class DiscountRule:
    """折扣规则结果"""
    action: Action
    discount_rate: Optional[float] = None
    tier: Optional[int] = None
    discount_range: Optional[list[float]] = None
    exemption_type: Optional[str] = None
    exemption_reason: Optional[str] = None
    reasoning_path: ReasoningPath = ReasoningPath.FAST
    reasoning: str = ""

    def to_dict(self) -> dict:
        result = {
            "action": self.action.value,
            "reasoning_path": self.reasoning_path.value,
            "reasoning": self.reasoning,
        }
        if self.discount_rate is not None:
            result["discount_rate"] = self.discount_rate
        if self.tier is not None:
            result["tier"] = self.tier
        if self.discount_range is not None:
            result["discount_range"] = self.discount_range
        if self.exemption_type is not None:
            result["exemption_type"] = self.exemption_type
        if self.exemption_reason is not None:
            result["exemption_reason"] = self.exemption_reason
        return result


class FastPathRuleEngine:
    """
    Fast Path 规则引擎 — 毫秒级确定性推理

    规则优先级：
    1. 豁免检查 → 直接返回 EXEMPTED
    2. 已过期 → 返回 NO_ACTION
    3. 库存调整 → 激进折扣
    4. 正常折扣计算
    """

    def evaluate(self, product: dict) -> DiscountRule:
        """
        评估单个商品的折扣规则。

        Args:
            product: 商品字典，应包含：
                - product_id: 商品ID
                - name: 商品名称
                - expiry_date: 到期日期 (YYYY-MM-DD)
                - days_left: 剩余天数（可选，计算得出）
                - category: 品类
                - stock: 库存量
                - is_imported: 是否进口（可选）
                - is_organic: 是否有机（可选）
                - is_promoted: 是否已促销（可选）
                - arrival_days: 到货天数（可选）

        Returns:
            DiscountRule: 折扣规则结果
        """
        import time
        start_ms = time.time() * 1000

        # 1. 解析商品信息
        product_id = product.get("product_id", "UNKNOWN")
        product_name = product.get("name", "商品")

        # 计算 days_left
        days_left = product.get("days_left")
        if days_left is None:
            expiry_str = product.get("expiry_date")
            if expiry_str:
                try:
                    expiry = date.fromisoformat(expiry_str)
                    days_left = (expiry - date.today()).days
                except (ValueError, TypeError):
                    days_left = 999
            else:
                days_left = 999

        category = product.get("category", "")
        stock = product.get("stock", 0)

        # 2. 豁免检查
        exemption = check_product_exemption_from_json(product)
        if exemption:
            elapsed_ms = time.time() * 1000 - start_ms
            logger.debug(f"[FastPath] {product_id} exempted: {exemption['exemption_type']} ({elapsed_ms:.1f}ms)")
            return DiscountRule(
                action=Action.EXEMPTED,
                exemption_type=exemption["exemption_type"],
                exemption_reason=exemption["exemption_reason"],
                reasoning_path=ReasoningPath.FAST,
                reasoning=f"【{product_name}】{exemption['exemption_reason']}",
            )

        # 3. 已过期检查
        if days_left < 0:
            elapsed_ms = time.time() * 1000 - start_ms
            logger.debug(f"[FastPath] {product_id} expired: {days_left} days ({elapsed_ms:.1f}ms)")
            return DiscountRule(
                action=Action.NO_ACTION,
                reasoning_path=ReasoningPath.FAST,
                reasoning=f"【{product_name}】已过期 {abs(days_left)} 天，无法折扣",
            )

        # 4. 超过最大临期天数（不做折扣处理）
        if days_left > 30:
            elapsed_ms = time.time() * 1000 - start_ms
            logger.debug(f"[FastPath] {product_id} not near expiry: {days_left} days ({elapsed_ms:.1f}ms)")
            return DiscountRule(
                action=Action.NO_ACTION,
                reasoning_path=ReasoningPath.FAST,
                reasoning=f"【{product_name}】剩余 {days_left} 天，未达到临期处理标准",
            )

        # 5. 正常折扣计算
        tier, rec_rate, discount_range = get_fallback_tier(days_left)

        # 6. 库存调整：高库存 + 短有效期 → 激进折扣
        final_rate = rec_rate
        if stock > HIGH_STOCK_THRESHOLD and days_left <= HIGH_URGENCY_DAYS:
            final_rate = min(rec_rate * STOCK_ADJUSTMENT_RATE, MAX_AGGRESSIVE_DISCOUNT)
            reasoning_extra = f"；高库存({stock}) + 短有效期({days_left}天) → 激进折扣"
        else:
            reasoning_extra = ""

        # 7. 判断是否需要审批
        min_rate, max_rate = discount_range
        if final_rate < min_rate:
            action = Action.NEEDS_APPROVAL
            reasoning_suffix = f"，折扣率 {final_rate*100:.0f}% 低于下限，需审批"
        else:
            action = Action.APPLY_DISCOUNT
            reasoning_suffix = ""

        elapsed_ms = time.time() * 1000 - start_ms
        logger.debug(f"[FastPath] {product_id} evaluated: {action.value}, rate={final_rate:.2f} ({elapsed_ms:.1f}ms)")

        return DiscountRule(
            action=action,
            discount_rate=final_rate,
            tier=tier,
            discount_range=discount_range,
            reasoning_path=ReasoningPath.FAST,
            reasoning=(
                f"【{product_name}】剩余 {days_left} 天未售出，"
                f"匹配 T{tier} 折扣区间 {min_rate*100:.0f}%-{max_rate*100:.0f}%，"
                f"建议折扣率 {final_rate*100:.0f}%{reasoning_extra}{reasoning_suffix}"
            ),
        )

    def evaluate_batch(self, products: list[dict]) -> list[DiscountRule]:
        """
        批量评估商品折扣规则。

        Args:
            products: 商品列表

        Returns:
            list[DiscountRule]: 每个商品的折扣规则结果
        """
        return [self.evaluate(p) for p in products]


class ReasoningEngine:
    """
    三级推理引擎统一入口

    自动选择推理路径：
    - Fast Path: 确定性规则，毫秒级
    - Medium Path: OWL 推理，百毫秒级
    - Slow Path: LLM Agent，秒级
    """

    def __init__(self):
        self.fast_path = FastPathRuleEngine()

    def reason(self, query: str, context: Optional[dict] = None) -> dict:
        """
        统一推理入口。

        Args:
            query: 自然语言查询
            context: 推理上下文（商品信息等）

        Returns:
            dict: 推理结果
        """
        query_lower = query.lower()

        # Fast Path 关键词
        if any(kw in query_lower for kw in ["临期", "打折", "折扣", "到期"]):
            if "豁免" not in query_lower and "缺货" not in query_lower and "为什么" not in query_lower:
                if context and "product" in context:
                    return self.fast_path.evaluate(context["product"]).to_dict()

        # Medium Path 关键词
        if any(kw in query_lower for kw in ["缺货", "销量", "品类", "所有"]):
            # TODO: 实现 Medium Path
            return {"error": "Medium Path not yet implemented", "path": ReasoningPath.MEDIUM.value}

        # Slow Path: 复杂推理
        if any(kw in query_lower for kw in ["为什么", "分析", "建议", "比较", "预测"]):
            # TODO: 实现 Slow Path (LLM Agent)
            return {"error": "Slow Path not yet implemented", "path": ReasoningPath.SLOW.value}

        # 默认使用 Fast Path
        if context and "product" in context:
            return self.fast_path.evaluate(context["product"]).to_dict()

        return {"error": "No context provided", "path": ReasoningPath.FAST.value}


# 全局单例
_reasoning_engine: Optional[ReasoningEngine] = None


def get_reasoning_engine() -> ReasoningEngine:
    """获取推理引擎单例"""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = ReasoningEngine()
    return _reasoning_engine
