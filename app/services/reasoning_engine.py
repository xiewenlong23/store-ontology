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


class MediumPathRuleEngine:
    """
    Medium Path — OWL RL 语义推理

    适用场景：
    - "查找所有缺货且销量高的生鲜 SKU"
    - "哪些品类最近7天有库存事件"
    - "统计各品类临期商品占比"
    - SPARQL + 本体隐含知识推理

    性能目标：百毫秒级（<500ms）
    """

    def __init__(self):
        from app.services.sparql_service import SPARQLService
        self._sparql = SPARQLService()

    def evaluate(self, query: str, context: Optional[dict] = None) -> DiscountRule:
        """
        评估查询，返回 DiscountRule（兼容接口）。

        对于 Medium Path 不直接返回折扣，而是返回语义查询结果。
        """
        query_lower = query.lower()

        if "缺货" in query_lower or "库存不足" in query_lower:
            return self._query_out_of_stock(query_lower, context)
        if "销量" in query_lower and ("高" in query_lower or "低" in query_lower):
            return self._query_sales_volume(query_lower, context)
        if "临期" in query_lower and "品类" in query_lower:
            return self._query_category_expiry(query_lower, context)
        if "所有" in query_lower or "统计" in query_lower:
            return self._query_all_products(query_lower, context)

        # 默认：返回帮助信息
        return DiscountRule(
            action=Action.NO_ACTION,
            reasoning_path=ReasoningPath.MEDIUM,
            reasoning="Medium Path 就绪，请使用更具体的查询（缺货/销量/临期品类/统计）"
        )

    def _query_out_of_stock(self, query: str, context: Optional[dict]) -> DiscountRule:
        """查询缺货商品（stock <= threshold）"""
        threshold = 10  # 默认缺货阈值
        if context and "threshold" in context:
            threshold = context["threshold"]

        from app.services.data import get_data_service
        products = get_data_service().load_all_products()
        out_of_stock = [
            p for p in products
            if p.get("stock", 0) <= threshold and not p.get("in_reduction", False)
        ]

        if not out_of_stock:
            return DiscountRule(
                action=Action.NO_ACTION,
                reasoning_path=ReasoningPath.MEDIUM,
                reasoning=f"当前没有缺货商品（阈值 ≤{threshold}件）"
            )

        # 按库存升序排列，取前5
        out_of_stock.sort(key=lambda p: p.get("stock", 0))
        top5 = out_of_stock[:5]

        lines = [f"发现 {len(out_of_stock)} 件缺货商品，需要补货："]
        for p in top5:
            stock = p.get("stock", 0)
            name = p.get("name", "未知")
            cat = p.get("category", "")
            lines.append(f"- {name}（{cat}）：库存 {stock} 件")
        if len(out_of_stock) > 5:
            lines.append(f"...还有 {len(out_of_stock) - 5} 件")

        return DiscountRule(
            action=Action.APPLY_DISCOUNT,
            reasoning_path=ReasoningPath.MEDIUM,
            reasoning="\n".join(lines)
        )

    def _query_sales_volume(self, query: str, context: Optional[dict]) -> DiscountRule:
        """
        查询高销量/低销量商品。

        注意：products.json 中无销量字段，以库存模拟：
        - 高销量 → 低库存（卖得快）
        - 低销量 → 高库存（卖得慢）
        """
        from app.services.data import get_data_service
        products = get_data_service().load_all_products()

        # 过滤临期商品
        from datetime import date
        today = date.today()
        near_expiry = []
        for p in products:
            expiry_str = p.get("expiry_date")
            if not expiry_str:
                continue
            try:
                expiry = date.fromisoformat(expiry_str)
                days_left = (expiry - today).days
                if 0 <= days_left <= 7:
                    near_expiry.append({**p, "days_left": days_left})
            except ValueError:
                continue

        if not near_expiry:
            return DiscountRule(
                action=Action.NO_ACTION,
                reasoning_path=ReasoningPath.MEDIUM,
                reasoning="最近7天没有临期商品"
            )

        # 高销量（低库存）+ 临期
        if "高" in query:
            near_expiry.sort(key=lambda p: p.get("stock", 999))
            top5 = near_expiry[:5]
            lines = ["高销量临期商品（库存低 = 卖得快）："]
            for p in top5:
                lines.append(
                    f"- {p.get('name', '未知')}：库存 {p.get('stock', 0)} 件，"
                    f"剩余 {p.get('days_left')} 天"
                )
        else:
            # 低销量（高库存）+ 临期
            near_expiry.sort(key=lambda p: p.get("stock", 0), reverse=True)
            top5 = near_expiry[:5]
            lines = ["低销量临期商品（库存高 = 卖得慢）："]
            for p in top5:
                lines.append(
                    f"- {p.get('name', '未知')}：库存 {p.get('stock', 0)} 件，"
                    f"剩余 {p.get('days_left')} 天"
                )

        return DiscountRule(
            action=Action.APPLY_DISCOUNT,
            reasoning_path=ReasoningPath.MEDIUM,
            reasoning="\n".join(lines)
        )

    def _query_category_expiry(self, query: str, context: Optional[dict]) -> DiscountRule:
        """统计各品类临期商品数量"""
        from collections import Counter
        from app.services.data import get_data_service
        from datetime import date

        products = get_data_service().load_all_products()
        today = date.today()
        category_counts = Counter()

        for p in products:
            expiry_str = p.get("expiry_date")
            if not expiry_str:
                continue
            try:
                expiry = date.fromisoformat(expiry_str)
                days_left = (expiry - today).days
                if 0 <= days_left <= 3:
                    cat = p.get("category", "未知")
                    category_counts[cat] += 1
            except ValueError:
                continue

        if not category_counts:
            return DiscountRule(
                action=Action.NO_ACTION,
                reasoning_path=ReasoningPath.MEDIUM,
                reasoning="各品类临期商品数量均为0，库存都很新鲜"
            )

        lines = ["各品类临期商品（≤3天）统计："]
        for cat, cnt in category_counts.most_common():
            lines.append(f"- {cat}: {cnt} 件")

        return DiscountRule(
            action=Action.APPLY_DISCOUNT,
            reasoning_path=ReasoningPath.MEDIUM,
            reasoning="\n".join(lines)
        )

    def _query_all_products(self, query: str, context: Optional[dict]) -> DiscountRule:
        """全量商品统计"""
        from app.services.data import get_data_service
        from datetime import date
        from collections import Counter

        products = get_data_service().load_all_products()
        today = date.today()

        total = len(products)
        expired = 0
        near_expiry = 0  # <= 3 days
        upcoming = 0     # 4-7 days
        categories = Counter()

        for p in products:
            expiry_str = p.get("expiry_date")
            if not expiry_str:
                continue
            try:
                expiry = date.fromisoformat(expiry_str)
                days_left = (expiry - today).days
            except ValueError:
                continue

            cat = p.get("category", "未知")
            categories[cat] += 1

            if days_left < 0:
                expired += 1
            elif days_left <= 3:
                near_expiry += 1
            elif days_left <= 7:
                upcoming += 1

        lines = [
            f"商品总数：{total} 件",
            f"  - 已过期：{expired} 件",
            f"  - 临期（≤3天）：{near_expiry} 件",
            f"  - 即将到期（4-7天）：{upcoming} 件",
            "",
            "各品类商品数量："
        ]
        for cat, cnt in categories.most_common():
            lines.append(f"  - {cat}: {cnt} 件")

        return DiscountRule(
            action=Action.APPLY_DISCOUNT,
            reasoning_path=ReasoningPath.MEDIUM,
            reasoning="\n".join(lines)
        )


class SlowPathRuleEngine:
    """
    Slow Path - LLM Agent multi-step reasoning helper engine

    Use cases:
    - "Why is this product discounted at 50%?"
    - "Analyze recent near-expiry product handling suggestions"
    - "Compare expiry situation across categories"
    - "Predict which products will become near-expiry next week"
    """

    def __init__(self):
        self._fast_path = FastPathRuleEngine()
        self._medium_path = MediumPathRuleEngine()

    def evaluate(self, query: str, context: Optional[dict] = None) -> DiscountRule:
        query_lower = query.lower()

        if "为什么" in query_lower:
            return self._explain_discount(query_lower, context)
        if "分析" in query_lower or "建议" in query_lower:
            return self._analyze_suggest(query_lower, context)
        if "比较" in query_lower:
            return self._compare(query_lower, context)
        if "预测" in query_lower:
            return self._predict(query_lower, context)

        return self._fallback(query_lower, context)

    def _explain_discount(self, query: str, context: Optional[dict]) -> DiscountRule:
        if not context or "product" not in context:
            return DiscountRule(
                action=Action.NO_ACTION,
                reasoning_path=ReasoningPath.SLOW,
                reasoning="无法解释：缺少商品信息。请先查询商品详情。"
            )

        product = context["product"]
        fast_result = self._fast_path.evaluate(product)

        exemption_type = fast_result.exemption_type
        exemption_reason = fast_result.exemption_reason
        discount_rate = fast_result.discount_rate

        days_left = product.get("days_left")
        if days_left is None:
            expiry_str = product.get("expiry_date")
            if expiry_str:
                from datetime import date
                try:
                    days_left = (date.fromisoformat(expiry_str) - date.today()).days
                except ValueError:
                    days_left = 999

        product_name = product.get("name", "商品")

        if fast_result.action == Action.EXEMPTED:
            reason = exemption_reason or "豁免规则"
            reasoning = "【%s】不参与打折：%s。豁免类型：%s。" % (product_name, reason, exemption_type)
        elif fast_result.action == Action.NO_ACTION:
            if days_left is not None and days_left < 0:
                reasoning = "【%s】已过期 %d 天，按照规则不能打折。" % (product_name, abs(days_left))
            else:
                reasoning = "【%s】剩余保质期充足（%d天），暂不参与临期处理。" % (product_name, days_left)
        elif fast_result.action == Action.NEEDS_APPROVAL:
            rate_pct = discount_rate * 100 if discount_rate else 0
            reasoning = "【%s】建议折扣率 %.0f%% 低于品类下限，需要店长审批后才能执行。" % (product_name, rate_pct)
        else:
            tier = fast_result.tier
            disc_range = fast_result.discount_range or []
            min_r = disc_range[0] if disc_range else 0
            max_r = disc_range[1] if disc_range else 0
            rate_pct = discount_rate * 100 if discount_rate else 0
            reasoning = "【%s】剩余 %d 天未售出，匹配 T%d 折扣区间（%.0f%%-%.0f%%），建议折扣率 %.0f%%。" % (
                product_name, days_left, tier, min_r * 100, max_r * 100, rate_pct
            )
            stock = product.get("stock", 0)
            if stock > 100 and days_left is not None and days_left <= 2:
                reasoning += "高库存（%d件）+ 短有效期 -> 建议更激进折扣。" % stock

        return DiscountRule(
            action=Action.NO_ACTION,
            reasoning_path=ReasoningPath.SLOW,
            reasoning=reasoning
        )

    def _analyze_suggest(self, query: str, context: Optional[dict]) -> DiscountRule:
        from app.services.data import get_data_service
        from datetime import date

        products = get_data_service().load_all_products()
        today = date.today()

        critical = []
        urgent = []
        upcoming = []

        for p in products:
            expiry_str = p.get("expiry_date")
            if not expiry_str:
                continue
            try:
                expiry = date.fromisoformat(expiry_str)
                days_left = (expiry - today).days
            except ValueError:
                continue

            if p.get("in_reduction"):
                continue

            if days_left <= 1:
                critical.append(p)
            elif days_left <= 3:
                urgent.append(p)
            elif days_left <= 7:
                upcoming.append(p)

        lines = ["临期商品分析报告", ""]

        if not critical and not urgent and not upcoming:
            lines.append("当前没有需要处理的临期商品，库存状态良好。")
            return DiscountRule(
                action=Action.NO_ACTION,
                reasoning_path=ReasoningPath.SLOW,
                reasoning="\n".join(lines)
            )

        if critical:
            lines.append("紧急（1天内）：%d 件" % len(critical))
            for p in critical[:3]:
                pname = p.get("name", "未知")
                pcat = p.get("category", "")
                pdays = p.get("days_left", 0)
                lines.append("  - %s（%s），剩余 %d 天" % (pname, pcat, pdays))
            if len(critical) > 3:
                lines.append("  ...还有 %d 件" % (len(critical) - 3))
            lines.append("  -> 建议立即打折处理（7折以上）")

        if urgent:
            lines.append("较急（2-3天）：%d 件" % len(urgent))
            for p in urgent[:3]:
                pname = p.get("name", "未知")
                pcat = p.get("category", "")
                pdays = p.get("days_left", 0)
                lines.append("  - %s（%s），剩余 %d 天" % (pname, pcat, pdays))
            if len(urgent) > 3:
                lines.append("  ...还有 %d 件" % (len(urgent) - 3))
            lines.append("  -> 建议尽快打折（5-7折）")

        if upcoming:
            lines.append("预警（4-7天）：%d 件" % len(upcoming))
            lines.append("  -> 建议持续关注，提前准备促销")

        from app.services.inventory_service import check_product_exemption_from_json
        exempted = [p for p in critical + urgent if check_product_exemption_from_json(p)]
        if exempted:
            lines.append("\n其中 %d 件豁免商品不参与打折" % len(exempted))

        total_actionable = len(critical) + len(urgent)
        if total_actionable > 0:
            lines.append("\n总计 %d 件商品需要处理（不含豁免）" % total_actionable)

        return DiscountRule(
            action=Action.APPLY_DISCOUNT if total_actionable > 0 else Action.NO_ACTION,
            reasoning_path=ReasoningPath.SLOW,
            reasoning="\n".join(lines)
        )

    def _compare(self, query: str, context: Optional[dict]) -> DiscountRule:
        from app.services.data import get_data_service
        from datetime import date

        products = get_data_service().load_all_products()
        today = date.today()

        category_data = {}
        for p in products:
            expiry_str = p.get("expiry_date")
            if not expiry_str:
                continue
            try:
                expiry = date.fromisoformat(expiry_str)
                days_left = (expiry - today).days
            except ValueError:
                continue

            cat = p.get("category", "未知")
            if cat not in category_data:
                category_data[cat] = {"critical": 0, "urgent": 0, "upcoming": 0}
            if days_left <= 1:
                category_data[cat]["critical"] += 1
            elif days_left <= 3:
                category_data[cat]["urgent"] += 1
            elif days_left <= 7:
                category_data[cat]["upcoming"] += 1

        if not category_data:
            return DiscountRule(
                action=Action.NO_ACTION,
                reasoning_path=ReasoningPath.SLOW,
                reasoning="暂无商品数据可供比较"
            )

        lines = ["临期商品品类对比", ""]
        has_data = False
        for cat, data in sorted(category_data.items(), key=lambda x: x[1]["critical"] + x[1]["urgent"], reverse=True):
            if data["critical"] + data["urgent"] == 0:
                continue
            has_data = True
            total = data["critical"] + data["urgent"]
            tag = "紧急" if data["critical"] > 0 else "较急"
            lines.append("%s：%s %d 件（紧急%d，较急%d）" % (cat, tag, total, data["critical"], data["urgent"]))

        if not has_data:
            lines.append("所有品类临期商品数量为0，库存状态良好。")

        return DiscountRule(
            action=Action.APPLY_DISCOUNT,
            reasoning_path=ReasoningPath.SLOW,
            reasoning="\n".join(lines)
        )

    def _predict(self, query: str, context: Optional[dict]) -> DiscountRule:
        from app.services.data import get_data_service
        from datetime import date, timedelta

        products = get_data_service().load_all_products()
        today = date.today()

        upcoming = []
        for p in products:
            expiry_str = p.get("expiry_date")
            if not expiry_str:
                continue
            try:
                expiry = date.fromisoformat(expiry_str)
                days_left = (expiry - today).days
            except ValueError:
                continue

            if 3 < days_left <= 7 and not p.get("in_reduction"):
                upcoming.append({**p, "days_left": days_left})

        if not upcoming:
            return DiscountRule(
                action=Action.NO_ACTION,
                reasoning_path=ReasoningPath.SLOW,
                reasoning="未来7天内没有即将变成临期的商品。"
            )

        upcoming.sort(key=lambda p: p.get("days_left", 999))
        lines = ["未来7天预警：%d 件商品即将临期" % len(upcoming), ""]
        for p in upcoming[:5]:
            pname = p.get("name", "未知")
            pcat = p.get("category", "")
            pdays = p.get("days_left")
            lines.append("- %s（%s）：预计 %d 天后到期" % (pname, pcat, pdays))
        if len(upcoming) > 5:
            lines.append("...还有 %d 件" % (len(upcoming) - 5))

        return DiscountRule(
            action=Action.APPLY_DISCOUNT,
            reasoning_path=ReasoningPath.SLOW,
            reasoning="\n".join(lines)
        )

    def _fallback(self, query: str, context: Optional[dict]) -> DiscountRule:
        medium_result = self._medium_path.evaluate(query, context)
        return medium_result


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
        self.medium_path = MediumPathRuleEngine()
        self.slow_path = SlowPathRuleEngine()

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

        # Slow Path: 复杂推理（优先级最高，防止被 Medium Path 截断）
        if any(kw in query_lower for kw in ["为什么", "分析", "建议", "比较", "预测"]):
            result = self.slow_path.evaluate(query, context)
            return result.to_dict()

        # Medium Path 关键词
        if any(kw in query_lower for kw in ["缺货", "销量", "品类", "所有", "统计"]):
            result = self.medium_path.evaluate(query, context)
            return result.to_dict()

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
