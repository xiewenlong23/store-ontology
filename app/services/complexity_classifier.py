#!/usr/bin/env python3
"""
复杂度分类器 — 区分简单查询和复杂推理

分层策略：
- Layer 1 (TTL Only): 简单结构化查询，< 50ms
- Layer 2 (TTL + LLM): 复杂推理（折扣推荐、风险评估、自然语言生成），500ms-2s

分类依据：
1. 是否需要多跳推理
2. 是否需要自然语言生成
3. 是否涉及风险/决策评估
4. 实体识别的复杂度
"""

import re
import logging
from enum import Enum
from typing import Optional

from app.models import ActionType

logger = logging.getLogger(__name__)


class QueryComplexity(str, Enum):
    """查询复杂度等级"""
    # 简单：直接查 TTL/SPARQL，无 LLM 推理
    SIMPLE = "simple"
    # 复杂：需要 LLM 参与推理、解释、生成
    COMPLEX = "complex"


# 简单查询模式（只查 TTL，不走 LLM）
SIMPLE_PATTERNS = [
    # 状态/列表查询
    r"^(有哪些|列出|查询|查看).*(临期|待出清|待确认|待执行|待复核)?.*商品",
    r"^(有哪些|列出|查询|查看).*任务",
    r"任务.*列表",
    r"任务.*状态",
    r"有多少.*临期",
    r"待出清.*商品.*列表",
    # 单一商品状态查询（不涉及折扣推荐）
    r"(商品|sku|单品).*状态",
    r"(商品|sku).*到期.*日期",
    r"(商品|sku).*品类",
    # 规则查询（只返回结构化规则，不推理）
    r"规则.*是什么",
    r".*品类.*规则",
    r"折扣.*规则",
    # 统计类
    r"今天.*多少.*任务",
    r"本周.*多少.*出清",
    r"有多少.*已.*完成",
]

# 复杂查询模式（必须走 LLM 推理）
COMPLEX_PATTERNS = [
    # 折扣推荐
    r"(该|应该?)?打.*折",
    r"推荐.*折扣",
    r"建议.*打.*折",
    r"怎么.*定价",
    r"折扣.*建议",
    r"这件.*多少钱",
    r"这个.*便宜.*多少",
    # 风险/决策评估
    r"(是否|要不要|能不能|可以?)自动确认",
    r"风险.*评估",
    r"会不会.*风险",
    r"要不要.*确认",
    r"是否.*人工.*复核",
    # 自然语言解释/生成
    r"为什么.*推荐",
    r"解释.*一下",
    r"说.*原因",
    r"给.*理由",
    r"详细.*说明",
    # 对比/选择
    r"哪个.*好",
    r"应该.*选择",
    r"还是.*打折",
    r"打折.*还是",
    # 综合推理
    r"综合.*分析",
    r"全面.*评估",
    r"综合.*考虑",
    r"结合.*情况",
]

# 关键词：表示需要 LLM
LLM_INDICATOR_KEYWORDS = [
    "为什么", "怎么", "如何", "是不是", "该不该",
    "建议", "推荐", "评估", "分析", "判断",
    "风险", "决策", "理由", "原因", "解释",
]


class ComplexityClassifier:
    """
    查询复杂度分类器

    策略：
    1. 优先用正则匹配 COMPLEX_PATTERNS（宁可误判走 LLM，也要保证质量）
    2. 其次用正则匹配 SIMPLE_PATTERNS
    3. 检查 LLM_INDICATOR_KEYWORDS
    4. 无法判断时默认走 Layer 2（复杂）
    """

    def __init__(self, llm=None):
        self._llm = llm

    def classify(self, user_input: str) -> QueryComplexity:
        """
        分类用户输入的复杂度

        Args:
            user_input: 店长的自然语言输入

        Returns:
            QueryComplexity: SIMPLE 或 COMPLEX
        """
        text = user_input.strip()

        # Step 1: 检查是否匹配复杂查询模式
        for pattern in COMPLEX_PATTERNS:
            if re.search(pattern, text):
                logger.debug(f"[ComplexityClassifier] Matched COMPLEX pattern: {pattern}")
                return QueryComplexity.COMPLEX

        # Step 2: 检查是否有复杂关键词
        for keyword in LLM_INDICATOR_KEYWORDS:
            if keyword in text:
                logger.debug(f"[ComplexityClassifier] Found LLM indicator: {keyword}")
                return QueryComplexity.COMPLEX

        # Step 3: 检查是否匹配简单查询模式
        for pattern in SIMPLE_PATTERNS:
            if re.search(pattern, text):
                logger.debug(f"[ComplexityClassifier] Matched SIMPLE pattern: {pattern}")
                return QueryComplexity.SIMPLE

        # Step 4: 无法判断，默认走 Layer 2（复杂）
        # 这是保守策略：宁可慢一点，也要保证推理质量
        logger.debug(f"[ComplexityClassifier] Uncertain, defaulting to COMPLEX")
        return QueryComplexity.COMPLEX

    def classify_with_reason(self, user_input: str) -> tuple[QueryComplexity, str]:
        """
        分类并返回原因

        Returns:
            (complexity, reason)
        """
        text = user_input.strip()

        for pattern in COMPLEX_PATTERNS:
            if re.search(pattern, text):
                return QueryComplexity.COMPLEX, f"匹配复杂模式: {pattern}"

        for keyword in LLM_INDICATOR_KEYWORDS:
            if keyword in text:
                return QueryComplexity.COMPLEX, f"包含复杂关键词: {keyword}"

        for pattern in SIMPLE_PATTERNS:
            if re.search(pattern, text):
                return QueryComplexity.SIMPLE, f"匹配简单模式: {pattern}"

        return QueryComplexity.COMPLEX, "无法判断，默认复杂"


# 全局单例
_classifier_instance: Optional[ComplexityClassifier] = None


def get_complexity_classifier() -> ComplexityClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = ComplexityClassifier()
    return _classifier_instance
