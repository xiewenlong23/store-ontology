from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import logging
import re

from app.agent.store_brain_agent import (
    get_store_brain_agent,
    init_store_brain_agent,
    StoreBrainAgent,
)
from app.services.complexity_classifier import get_complexity_classifier, QueryComplexity
from app.services.ttl_llm_reasoning import (
    ttl_query_pending_skus,
    ttl_query_clearance_rules,
    ttl_query_tasks,
    reason_discount_llm,
    assess_risk_llm,
    generate_chat_response,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Unified TTL+LLM Chat Endpoint — Hermes 风格架构
# ============================================================

class UnifiedChatRequest(BaseModel):
    message: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    expiry_date: Optional[str] = None
    stock: Optional[int] = None
    skip_llm: bool = False  # 强制 TTL-only（调试用）


class UnifiedChatResponse(BaseModel):
    response: str  # 自然语言响应
    tool_name: Optional[str] = None
    tool_result: Optional[dict] = None
    success: bool = True
    needs_confirmation: bool = False


@router.post("/unified-chat", response_model=UnifiedChatResponse)
def unified_chat(req: UnifiedChatRequest):
    """
    统一对话入口 — Hermes 工具注册 + LLM 调度架构。

    流程：
    1. 接收用户自然语言输入
    2. AgentExecutor 根据工具注册表 + LLM 决定调用哪个工具
    3. 工具执行（TTL 查询或业务操作）
    4. AgentExecutor 生成自然语言响应
    5. 返回给前端直接展示

    架构参考 Hermes：
        用户 → LLM理解意图 → 调用工具 → 结果返回LLM → LLM组织语言 → 返回用户
    """
    # 导入工具注册（触发注册）
    import app.tools.store_tools  # noqa: F401

    try:
        from app.services.agent_executor import AgentExecutor

        # 构建上下文（从请求中提取可用的商品/任务信息）
        context = {}
        if req.product_id:
            context["product_id"] = req.product_id
        if req.product_name:
            context["product_name"] = req.product_name
        if req.category:
            context["category"] = req.category
        if req.expiry_date:
            context["expiry_date"] = req.expiry_date
        if req.stock is not None:
            context["stock"] = req.stock

        # AgentExecutor 执行
        executor = AgentExecutor()
        result = executor.execute(req.message, context=context if context else None)

        return UnifiedChatResponse(
            response=result.get("response", "抱歉，处理失败。"),
            tool_name=result.get("tool_name"),
            tool_result=result.get("tool_result"),
            success=result.get("success", False),
            needs_confirmation=result.get("needs_confirmation", False),
        )

    except ValueError as ve:
        raise HTTPException(
            status_code=503,
            detail=f"LLM not configured: {ve}. Set MINIMAX_API_KEY environment variable.",
        )
    except Exception as e:
        logger.error(f"[UnifiedChat] error: {e}")
        raise HTTPException(status_code=500, detail=f"Unified chat error: {e}")


# ============================================================
# Legacy Endpoints (kept for backward compatibility)
# ============================================================


class AgentChatRequest(BaseModel):
    message: str
    api_key: Optional[str] = None


class AgentChatResponse(BaseModel):
    response: str
    agent_used: bool = True


@router.post("/chat", response_model=AgentChatResponse)
def chat_with_agent(req: AgentChatRequest):
    """
    Natural language interface to StoreBrainAgent.

    The agent uses LangChain ReAct to:
    - Understand user intent (via MiniMax LLM)
    - Query ontology via SPARQL (via RDFLib)
    - Reason about discount and tasks
    - Return actionable recommendations

    Example queries:
    - "查询所有临期商品"
    - "给出折扣建议"
    - "查看任务 T-20260419-0001 的状态"
    """
    try:
        # Re-initialize if api_key provided (allows per-request override)
        if req.api_key:
            init_store_brain_agent(api_key=req.api_key)

        agent = get_store_brain_agent()
        response = agent.run(req.message)
        return AgentChatResponse(response=response, agent_used=True)
    except ValueError as ve:
        # API key not configured
        raise HTTPException(
            status_code=503,
            detail=f"LLM not configured: {ve}. Set MINIMAX_API_KEY environment variable."
        )
    except Exception as e:
        logger.error(f"[Agent Router] chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")


@router.get("/tasks/pending")
def list_pending_tasks():
    """List all pending WorkTasks from the ontology."""
    try:
        from app.services.sparql_service import SPARQLService
        sparql = SPARQLService()
        results = sparql.get_all_tasks(limit=50)

        tasks = []
        for row in results:
            tasks.append({
                "task_id": str(row.taskId),
                "task_type": str(row.taskType).split("#")[-1],
                "task_status": str(row.taskStatus).split("#")[-1],
                "priority": str(row.taskPriority).split("#")[-1] if row.taskPriority else None,
                "created_at": str(row.createdAt) if row.createdAt else None,
                "due_time": str(row.dueTime) if row.dueTime else None,
            })
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as e:
        logger.error(f"[Agent Router] list_pending_tasks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class IntentClassifyRequest(BaseModel):
    message: str
    use_llm_fallback: bool = True


class IntentClassifyResponse(BaseModel):
    message: str
    action_type: str
    confidence: str  # "keyword" or "llm"


@router.post("/intent/classify", response_model=IntentClassifyResponse)
def classify_intent(req: IntentClassifyRequest):
    """
    将店长的自然语言输入分类为 ActionType。

    使用关键词快速匹配 + LLM 二次确认的混合策略。
    """
    try:
        from app.services.intent_classifier import get_intent_classifier
        classifier = get_intent_classifier()
        action_type = classifier.classify(req.message, use_llm_fallback=req.use_llm_fallback)

        # 判断匹配来源
        from app.services.intent_classifier import INTENT_KEYWORDS
        matched_keyword = False
        for patterns in INTENT_KEYWORDS.values():
            for pattern in patterns:
                if re.search(pattern, req.message.lower()):
                    matched_keyword = True
                    break
            if matched_keyword:
                break

        confidence = "keyword" if matched_keyword else "llm"

        return IntentClassifyResponse(
            message=req.message,
            action_type=action_type.value,
            confidence=confidence,
        )
    except Exception as e:
        logger.error(f"[Agent Router] intent classify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan-and-reason")
def scan_and_reason():
    """
    Perform a full scan of pending clearance SKUs and generate discount recommendations.

    This combines SPARQL queries with discount reasoning to produce
    actionable task recommendations.
    """
    try:
        from app.services.sparql_service import SPARQLService
        from datetime import date

        sparql = SPARQLService()
        skus = sparql.query_pending_clearance_skus()

        recommendations = []
        today = date.today()

        for row in skus:
            expiry_str = str(row.exp)
            try:
                expiry = date.fromisoformat(expiry_str)
                days_left = (expiry - today).days
            except Exception:
                continue

            if days_left < 0:
                continue

            category_uri = str(row.cat)
            rules = sparql.query_clearance_rules(category_uri)

            # Find matching tier
            matched = None
            for r in rules:
                if int(r.tierMin) <= days_left <= int(r.tierMax):
                    matched = r
                    break

            if matched:
                recommendations.append({
                    "sku_name": str(row.name),
                    "sku_code": str(row.code),
                    "quantity": int(row.qty),
                    "category": str(row.catName),
                    "days_left": days_left,
                    "recommended_discount": float(matched.recDiscount),
                    "discount_range": [float(matched.minDiscount), float(matched.maxDiscount)],
                    "urgency": str(matched.urgency).split("#")[-1],
                    "tier": str(matched.tier).split("#")[-1],
                })
            else:
                # Fallback
                recommendations.append({
                    "sku_name": str(row.name),
                    "sku_code": str(row.code),
                    "quantity": int(row.qty),
                    "category": str(row.catName),
                    "days_left": days_left,
                    "recommended_discount": None,
                    "reasoning": "无可用折扣规则",
                })

        return {
            "recommendations": recommendations,
            "total_skus_scanned": len(skus),
            "recommendations_count": len(recommendations),
        }
    except Exception as e:
        logger.error(f"[Agent Router] scan_and_reason error: {e}")
        raise HTTPException(status_code=500, detail=str(e))