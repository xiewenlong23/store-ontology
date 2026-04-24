#!/usr/bin/env python3
"""
意图分类器 - LLM理解店长自然语言 → ActionType

使用 MiniMax LLM 进行零样本分类，将用户输入分类到预定义的 ActionType。
"""

import logging
import re
from typing import Optional

from app.models import ActionType

logger = logging.getLogger(__name__)

# 关键词模式匹配（快速兜底）
INTENT_KEYWORDS = {
    ActionType.QUERY_PENDING: [
        r"临期", r"待出清", r"快过期", r"临期商品",
        r"还有.*临期", r"临期.*有哪些", r"商品.*临期",
        r"哪些.*要打折", r"查询.*商品", r"商品.*状态",
        r"显示", r"查看有哪些", r"现在有", r"商品.*列表",
    ],
    ActionType.QUERY_TASKS: [
        r"任务.*状态", r"还有.*任务", r"今日.*任务", r"全部.*任务",
        r"待.*处理", r"还有.*任务",
        r"查看.*任务", r"任务.*列表", r"有哪些.*任务",
        r"待.*确认", r"待.*执行", r"待.*复核",
        r"任务", r"task", r"工单", r"进度", r"状态",
    ],
    ActionType.QUERY_DISCOUNT: [
        r"折扣规则", r"打折规则", r"规则.*折扣",
        r"折扣.*表", r"打折.*表", r"哪些.*折扣",
        r"折扣", r"打折", r"建议.*折扣", r"降价",
        r"该打.*折", r"怎么.*定价", r"折扣.*建议",
        r"打.*折", r"多少折", r"建议.*折",
        r"嫩豆腐.*折", r".*打几折",
    ],
    ActionType.CREATE_TASK: [
        r"创建.*任务", r"新建.*任务", r"生成.*任务",
        r"发起.*出清", r"开始.*打折", r"执行.*出清",
        r"帮我.*出清", r"发起.*任务",
    ],
    ActionType.CONFIRM_TASK: [
        r"确认", r"审批", r"同意.*出清", r"通过.*任务",
        r"确认.*折扣", r"确认.*出清",
        r"同意.*打折",
    ],
    ActionType.EXECUTE_TASK: [
        r"执行", r"扫描", r"打印.*价签", r"已经.*扫描",
        r"完成.*扫描", r"价签.*打印",
        r"开始.*执行",
    ],
    ActionType.REVIEW_TASK: [
        r"复核", r"审核", r"售罄率", r"报告.*结果",
        r"任务.*闭环", r"完成.*复核",
        r"报告.*完成",
    ],
    ActionType.REPORT_COMPLETION: [
        r"完成", r"搞定了", r"卖完", r"售罄",
        r"报告.*完成", r"已.*执行", r"结束",
    ],
    ActionType.SCAN_INVENTORY: [
        r"扫描", r"盘点", r"全面.*检查", r"库存.*扫描",
        r"每日.*巡检", r"例行.*检查",
    ],
}


class IntentClassifier:
    """
    店长意图分类器

    使用关键词快速匹配 + LLM 二次确认的混合策略。
    优先使用关键词匹配，匹配失败时调用 LLM。
    """

    def __init__(self, llm=None):
        self._llm = llm

    def _keyword_match(self, message: str) -> Optional[ActionType]:
        """基于关键词的快速匹配"""
        message_lower = message.lower()
        for action_type, patterns in INTENT_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    logger.debug(f"[IntentClassifier] Keyword match: {action_type.value}")
                    return action_type
        return None

    def _llm_classify(self, message: str) -> ActionType:
        """使用 LLM 进行零样本分类，带指数退避重试（最多3次）"""
        if self._llm is None:
            from app.services.llm_service import get_minimax_llm
            self._llm = get_minimax_llm().llm

        prompt = f"""你是一个门店运营意图分类器。请将用户的输入分类到以下类别之一：

类别：
- query_pending: 查询临期待出清的商品
- query_tasks: 查询现有任务的状态/列表（含待确认/待执行/待复核）
- query_discount: 查询某商品的折扣建议
- create_task: 创建新的出清任务
- confirm_task: 确认/审批任务（同意出清方案）
- execute_task: 执行任务（扫描+打印价签）
- review_task: 复核任务（报告售罄率，任务闭环）
- report_completion: 报告任务完成
- scan_inventory: 扫描/盘点库存
- unknown: 无法分类

用户输入：「{message}」

只返回一个类别名称，不要解释。"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self._llm.invoke([{"role": "user", "content": prompt}])
                content = response.content.strip().lower()

                # 解析 LLM 返回
                for action_type in ActionType:
                    if action_type.value in content or action_type.name.lower() in content:
                        logger.info(f"[IntentClassifier] LLM classified: {action_type.value}")
                        return action_type

                logger.warning(f"[IntentClassifier] LLM returned unrecognized: {content}")
                return ActionType.UNKNOWN
            except Exception as e:
                logger.warning(f"[IntentClassifier] LLM classify attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # 指数退避：1s, 2s, 4s（线程池中执行，不阻塞事件循环）
                else:
                    logger.error(f"[IntentClassifier] LLM classify failed after {max_retries} attempts: {e}")
                    return ActionType.UNKNOWN

    def classify(self, message: str, use_llm_fallback: bool = True) -> ActionType:
        """
        分类用户输入

        Args:
            message: 店长的自然语言输入
            use_llm_fallback: 关键词匹配失败时是否使用 LLM

        Returns:
            ActionType 枚举值
        """
        # 1. 快速关键词匹配
        matched = self._keyword_match(message)
        if matched and matched != ActionType.UNKNOWN:
            return matched

        # 2. LLM 兜底
        if use_llm_fallback:
            return self._llm_classify(message)

        return ActionType.UNKNOWN


# 全局单例
_classifier_instance: Optional[IntentClassifier] = None


def get_intent_classifier() -> IntentClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance