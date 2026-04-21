#!/usr/bin/env python3
"""
StoreBrainAgent - LangChain ReAct 智能体
融合 MiniMax LLM + SPARQL 本体推理，执行门店运营任务

使用 langchain 1.x API: langchain.agents.create_agent (返回 CompiledStateGraph)
"""

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.services.sparql_service import SPARQLService

logger = logging.getLogger(__name__)


# ============================================================
# Conversation Memory
# ============================================================

@dataclass
class MessageRecord:
    """Single conversation message record."""
    role: str          # "user" or "assistant"
    content: str
    timestamp: str      # ISO format timestamp


@dataclass
class ConversationMemory:
    """
    In-memory conversation history with configurable max history.

    Maintains a rolling window of user/assistant message pairs
    for context-aware agent responses.
    """
    max_history: int = 20
    _history: deque = field(default_factory=lambda: deque(maxlen=20))

    def add_user_message(self, content: str, timestamp: Optional[str] = None) -> None:
        ts = timestamp or date.today().isoformat()
        self._history.append(MessageRecord(role="user", content=content, timestamp=ts))

    def add_assistant_message(self, content: str, timestamp: Optional[str] = None) -> None:
        ts = timestamp or date.today().isoformat()
        self._history.append(MessageRecord(role="assistant", content=content, timestamp=ts))

    def get_messages(self) -> list[dict]:
        """Return history as list of message dicts for LangChain."""
        return [
            {"role": m.role, "content": m.content}
            for m in self._history
        ]

    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()

    def __len__(self) -> int:
        return len(self._history)


# Global memory registry (per agent instance id)
_memory_by_agent: dict[int, ConversationMemory] = {}


def _get_memory(agent_id: int) -> ConversationMemory:
    """Get or create memory for a given agent instance id."""
    if agent_id not in _memory_by_agent:
        _memory_by_agent[agent_id] = ConversationMemory()
    return _memory_by_agent[agent_id]


# ============================================================
# Tool definitions
# ============================================================

@tool
def query_pending_skus() -> str:
    """Query all pending clearance SKUs from the ontology.

    Returns a list of SKUs that are in 'ClearanceStatusPending' state,
    meaning they are due for discount/reduction processing.

    Returns:
        JSON string with SKU list including name, code, quantity, expiry date, category.
    """
    sparql = SPARQLService()
    results = sparql.query_pending_clearance_skus()
    if not results:
        return json.dumps({"skus": [], "count": 0}, ensure_ascii=False)

    skus = []
    for row in results:
        skus.append({
            "sku_uri": str(row.sku),
            "name": str(row.name),
            "code": str(row.code),
            "quantity": int(row.qty),
            "expiry_date": str(row.exp),
            "category_uri": str(row.cat),
            "category_name": str(row.catName),
            "clearance_status": str(row.clearanceStatus).split("#")[-1],
        })
    return json.dumps({"skus": skus, "count": len(skus)}, ensure_ascii=False)


@tool
def query_clearance_rules(category_uri: str) -> str:
    """Query clearance rules for a specific category from the ontology.

    Args:
        category_uri: The category URI (e.g., so:FreshProduce)

    Returns:
        JSON string with applicable discount tiers and urgency levels.
    """
    sparql = SPARQLService()
    results = sparql.query_clearance_rules(category_uri)
    if not results:
        return json.dumps({"rules": [], "found": False}, ensure_ascii=False)

    rules = []
    for row in results:
        rules.append({
            "urgency": str(row.urgency).split("#")[-1],
            "tier": str(row.tier).split("#")[-1],
            "tier_min_days": int(row.tierMin),
            "tier_max_days": int(row.tierMax),
            "recommended_discount": float(row.recDiscount),
            "min_discount": float(row.minDiscount),
            "max_discount": float(row.maxDiscount),
        })
    return json.dumps({"rules": rules, "found": True}, ensure_ascii=False)


@tool
def query_worktask(task_id: str) -> str:
    """Query a specific WorkTask by its task ID.

    Args:
        task_id: The task identifier (e.g., "T-20260419-0001")

    Returns:
        JSON string with task details including status, type, priority, timestamps.
    """
    sparql = SPARQLService()
    results = sparql.get_task_by_id(task_id)
    if not results:
        return json.dumps({"task": None, "found": False}, ensure_ascii=False)

    row = results[0]
    task = {
        "task_uri": str(row.task),
        "task_id": str(row.taskId),
        "task_type": str(row.taskType).split("#")[-1] if "#" in str(row.taskType) else str(row.taskType),
        "task_status": str(row.taskStatus).split("#")[-1] if "#" in str(row.taskStatus) else str(row.taskStatus),
        "task_priority": str(row.taskPriority).split("#")[-1] if hasattr(row, "taskPriority") and row.taskPriority else None,
        "created_at": str(row.createdAt) if hasattr(row, "createdAt") and row.createdAt else None,
        "due_time": str(row.dueTime) if hasattr(row, "dueTime") and row.dueTime else None,
        "completed_at": str(row.completedAt) if hasattr(row, "completedAt") and row.completedAt else None,
    }
    return json.dumps({"task": task, "found": True}, ensure_ascii=False)


@tool
def list_worktasks(limit: int = 20) -> str:
    """List all WorkTasks from the ontology.

    Args:
        limit: Maximum number of tasks to return (default 20)

    Returns:
        JSON string with list of tasks.
    """
    sparql = SPARQLService()
    results = sparql.get_all_tasks(limit=limit)
    if not results:
        return json.dumps({"tasks": [], "count": 0}, ensure_ascii=False)

    tasks = []
    for row in results:
        tasks.append({
            "task_uri": str(row.task),
            "task_id": str(row.taskId),
            "task_type": str(row.taskType).split("#")[-1] if "#" in str(row.taskType) else str(row.taskType),
            "task_status": str(row.taskStatus).split("#")[-1] if "#" in str(row.taskStatus) else str(row.taskStatus),
            "task_priority": str(row.taskPriority).split("#")[-1] if hasattr(row, "taskPriority") and row.taskPriority else None,
            "created_at": str(row.createdAt) if hasattr(row, "createdAt") and row.createdAt else None,
            "due_time": str(row.dueTime) if hasattr(row, "dueTime") and row.dueTime else None,
        })
    return json.dumps({"tasks": tasks, "count": len(tasks)}, ensure_ascii=False)


@tool
def reason_discount(sku_data: dict) -> str:
    """Reason about appropriate discount for a SKU based on days remaining.

    This tool implements the discount reasoning logic:
    - Match SKU's remaining shelf life to discount tiers
    - Consider category-specific urgency rules
    - Return recommended discount rate and reasoning

    Args:
        sku_data: dict with keys: name, code, quantity, expiry_date, category_uri, category_name

    Returns:
        JSON string with discount recommendation and reasoning.
    """
    try:
        expiry = date.fromisoformat(sku_data.get("expiry_date", ""))
        today = date.today()
        days_left = (expiry - today).days
    except Exception:
        return json.dumps({"error": "Invalid expiry date format", "days_left": None}, ensure_ascii=False)

    if days_left < 0:
        return json.dumps({
            "days_left": days_left,
            "recommended_discount": None,
            "reasoning": f"商品已过期 {abs(days_left)} 天，跳过",
            "tier": None,
            "urgency": None,
        }, ensure_ascii=False)

    # Query clearance rules for the category
    sparql = SPARQLService()
    category_uri = sku_data.get("category_uri", "")
    rule_results = sparql.query_clearance_rules(category_uri)

    if not rule_results:
        return _fallback_discount(sku_data, days_left)

    # Match tier by days
    tier_order = {
        "UrgencyCritical": 0,
        "UrgencyHigh": 1,
        "UrgencyMedium": 2,
        "UrgencyLow": 3,
        "UrgencyPreventive": 4,
    }

    matched = None
    best_urgency = None
    best_priority = 99

    for row in rule_results:
        tier_min = int(row.tierMin)
        tier_max = int(row.tierMax)
        if tier_min <= days_left <= tier_max:
            urgency_name = str(row.urgency).split("#")[-1]
            priority = tier_order.get(urgency_name, 99)
            if priority < best_priority:
                matched = row
                best_urgency = urgency_name
                best_priority = priority

    if matched:
        rec = float(matched.recDiscount)
        min_d = float(matched.minDiscount)
        max_d = float(matched.maxDiscount)
        tier_name = str(matched.tier).split("#")[-1]
        return json.dumps({
            "days_left": days_left,
            "sku_name": sku_data.get("name"),
            "recommended_discount": rec,
            "discount_range": [min_d, max_d],
            "tier": tier_name,
            "urgency": best_urgency,
            "reasoning": (
                f"剩余保质期 {days_left} 天，匹配 [{tier_name}]，"
                f"规则允许折扣 {min_d*100:.0f}%-{max_d*100:.0f}%，推荐 {rec*100:.0f}%"
            ),
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "days_left": days_left,
            "sku_name": sku_data.get("name"),
            "recommended_discount": None,
            "reasoning": f"剩余保质期 {days_left} 天，超出所有折扣层级适用范围，跳过",
            "tier": None,
            "urgency": None,
        }, ensure_ascii=False)


def _fallback_discount(sku_data: dict, days_left: int) -> str:
    """Fallback discount reasoning using hardcoded tiers"""
    if days_left <= 1:
        tier, rec = 1, 0.20
    elif days_left <= 3:
        tier, rec = 2, 0.40
    elif days_left <= 7:
        tier, rec = 3, 0.70
    elif days_left <= 14:
        tier, rec = 4, 0.85
    else:
        tier, rec = 5, 0.95

    return json.dumps({
        "days_left": days_left,
        "sku_name": sku_data.get("name"),
        "recommended_discount": rec,
        "discount_range": [0.10 * (tier - 1) + 0.10, 0.10 * (tier - 1) + 0.50] if tier else None,
        "tier": f"Tier{tier}",
        "urgency": "Medium",
        "reasoning": f"标准 tier T{tier} 定价（无本体规则时降级）",
    }, ensure_ascii=False)


# ============================================================
# StoreBrainAgent class
# ============================================================

SYSTEM_PROMPT = """你是门店自动化运营助手（StoreBrainAgent），负责管理临期商品出清任务。

## 角色定义
你是一个专业的门店运营助手，能够：
1. 通过 SPARQL 本体查询获取临期商品、折扣规则、任务状态
2. 基于剩余保质期计算合适的折扣推荐
3. 帮助店长管理工作任务生命周期

## 可用工具（严格按规范调用）
| 工具名 | 输入 | 输出 |
|--------|------|------|
| query_pending_skus | 无 | 待出清SKU列表（名称、编码、库存、到期日、品类） |
| query_clearance_rules | category_uri | 品类折扣规则（紧迫度、层级、折扣范围） |
| query_worktask | task_id | 任务详情（状态、类型、优先级、创建时间） |
| list_worktasks | limit=N | 工作任务列表（最多N条） |
| reason_discount | sku_data字典 | 折扣推荐结果（折扣率、推理过程） |

## 推理约束
- 必须先查询本体数据，再进行折扣推理
- 剩余保质期 ≤ 1 天的商品优先推荐深度折扣
- 库存 > 100 且有效期 ≤ 2 天时，折扣率额外下调 10%
- 无法匹配折扣规则时，使用分级折扣表兜底

## 输出格式（必须遵循）
1. 数据来源：本体的具体查询结果
2. 推理过程：剩余X天 → 匹配[TierX] → 折扣Y%
3. 行动建议：是否需要创建出清任务

## 错误处理
- API Key 未配置：返回友好提示"请配置 MINIMAX_API_KEY 环境变量"
- 本体查询失败：返回"暂时无法查询本体数据，请稍后重试"
- LLM 调用失败：返回"AI 服务暂时不可用，请联系管理员"
"""


class StoreBrainAgent:
    """
    LangChain ReAct Agent for store automation.

    Combines:
    - MiniMax LLM for natural language understanding
    - SPARQL/RDFLib for ontology querying
    - Discount reasoning tools

    Usage:
        agent = StoreBrainAgent()
        result = agent.run("查询所有临期商品并给出折扣建议")
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self._agent_graph = None

    def _init_agent(self):
        """Initialize the ReAct agent graph with tools and LLM"""
        llm = self._get_llm()

        tools = [
            query_pending_skus,
            query_clearance_rules,
            query_worktask,
            list_worktasks,
            reason_discount,
        ]

        agent_graph = create_agent(
            model=llm,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )
        return agent_graph

    def _get_llm(self) -> ChatOpenAI:
        """Get or create MiniMax LLM instance"""
        from app.services.llm_service import get_minimax_llm
        return get_minimax_llm().llm

    @property
    def agent_graph(self):
        if self._agent_graph is None:
            self._agent_graph = self._init_agent()
        return self._agent_graph

    def run(self, user_input: str, store_memory: bool = True) -> str:
        """
        Run the agent with a user query.

        Args:
            user_input: The natural language input from the user.
            store_memory: Whether to store this exchange in conversation history.
        """
        logger.info(f"[StoreBrainAgent] Input: {user_input}")

        # Build message list with history + current input
        messages = _get_memory(id(self)).get_messages()
        messages.append({"role": "user", "content": user_input})

        try:
            result = self.agent_graph.invoke({"messages": messages})
            output = result["messages"][-1].content
            logger.info(f"[StoreBrainAgent] Output: {output[:200]}...")

            if store_memory:
                memory = _get_memory(id(self))
                memory.add_user_message(user_input)
                memory.add_assistant_message(output)

            return output
        except Exception as e:
            logger.error(f"[StoreBrainAgent] Error: {e}")
            return f"Agent execution error: {e}"

    def get_conversation_history(self) -> list[dict]:
        """Return the conversation history for this agent."""
        return _get_memory(id(self)).get_messages()

    def clear_conversation_history(self) -> None:
        """Clear the conversation history for this agent."""
        _get_memory(id(self)).clear()


# Global singleton
_agent_instance: StoreBrainAgent | None = None


def get_store_brain_agent() -> StoreBrainAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = StoreBrainAgent()
    return _agent_instance


def init_store_brain_agent(api_key: str | None = None) -> StoreBrainAgent:
    global _agent_instance
    _agent_instance = StoreBrainAgent(api_key=api_key)
    return _agent_instance