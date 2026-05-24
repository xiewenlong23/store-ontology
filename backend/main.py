"""FastAPI 主入口 — 本体驱动 AI 门店助手

架构：
- 本体语义定义: ontology/store.ttl
- 本体解析器: ontology/parser.py → EntityRegistry
- 通用工具: ontology/tools.py (query_entity, create_entity, traverse_relation)
- Agent: LangGraph StateGraph + LangGraphAGUIAgent
- 前端: CopilotKit v1.57.4 via AG-UI 协议
"""

import os
import json
import warnings
import sys
from dotenv import load_dotenv

load_dotenv()

# 确保 ontology 模块可导入
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from typing import Annotated, List, Dict, Any, Optional
from typing_extensions import TypedDict

from copilotkit import LangGraphAGUIAgent
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
# ===== 导入本体驱动通用工具 =====
from ontology.tools import query_entity, traverse_relation, create_entity, update_entity, build_ontology_prompt, _registry

# ============ LLM 配置 ============

api_key = os.getenv("QWEN_API_KEY")
if not api_key:
    raise RuntimeError("QWEN_API_KEY 环境变量未设置")

base_url = os.getenv("QWEN_BASE_URL", "https://api.deepseek.com/v1")
model = os.getenv("QWEN_MODEL", "deepseek-chat")

llm = ChatOpenAI(
    model=model,
    api_key=api_key,
    base_url=base_url,
    temperature=0.7,
)


# ============ 专用业务工具 ============

@tool
def get_near_expiry_products(store_id: str = None) -> str:
    """获取指定门店的临期商品列表。"""
    from services.ontology_service import OntologyService
    from datetime import date

    ontology = OntologyService()
    if store_id:
        products = ontology.get_near_expiry_products_by_store(store_id)
    else:
        products = ontology.get_near_expiry_products()

    if not products:
        return f"门店 {store_id or '全部'} 暂无临期商品"

    result_lines = [f"门店 {store_id or '全部'} 临期商品列表："]
    today = date.today()
    for p in products:
        days_left = (p.expiry_date - today).days
        store = ontology.get_store(p.store_id)
        product = ontology.get_product(p.product_id)
        store_name = store.name if store else p.store_id
        product_name = product.name if product else p.product_id
        result_lines.append(
            f"  - {p.id}: {product_name} | {store_name} | "
            f"批次{p.batch_no} | 库存{p.stock_quantity} | "
            f"过期日{p.expiry_date} | 剩余{days_left}天 | "
            f"状态{p.status} | 折扣层级{p.discount_tier}"
        )
    return "\n".join(result_lines)


@tool
def create_clearance_task(store_id: str, product_id: str, discount: int) -> str:
    """为指定门店的临期商品创建出清任务（预览模式，实际创建需用户确认后调用 confirm_clearance_task）。

    调用后返回任务预览，LLM 应询问用户确认，确认后调用 confirm_clearance_task 完成创建。
    """
    from services.ontology_service import OntologyService

    ontology = OntologyService()
    store = ontology.get_store(store_id)
    if not store:
        return f"错误：门店 {store_id} 不存在"

    nep = ontology.get_near_expiry_product(product_id)
    if not nep:
        return f"错误：临期商品 {product_id} 不存在"
    if nep.store_id != store_id:
        return f"错误：临期商品 {product_id} 不属于门店 {store_id}"
    if nep.status == "expired":
        return f"错误：临期商品 {product_id} 已过期，无法创建出清任务"

    return (
        f"📋 出清任务预览（待确认）\n"
        f"门店: {store.name} ({store_id})\n"
        f"商品: {product_id}\n"
        f"数量: {nep.stock_quantity}\n"
        f"折扣: {discount}%\n"
        f"负责人: {store.manager_id}\n"
        f"\n请询问用户是否确认创建。用户回复确认后，调用 confirm_clearance_task("
        f"store_id='{store_id}', product_id='{product_id}', discount={discount}) 完成创建。"
    )


@tool
def confirm_clearance_task(store_id: str, product_id: str, discount: int) -> str:
    """用户确认后，实际创建出清任务。仅在用户明确回复"确认"/"好的"/"可以"后调用。
    
    Args:
        store_id: 门店ID
        product_id: 临期商品ID  
        discount: 折扣百分比(0-100)
    """
    from services.ontology_service import OntologyService
    from models.schemas import ClearanceTask, ClearanceParams, TaskStatus
    import uuid
    from datetime import datetime

    ontology = OntologyService()
    store = ontology.get_store(store_id)
    nep = ontology.get_near_expiry_product(product_id)

    task = ClearanceTask(
        id=f"task_{uuid.uuid4().hex[:8]}",
        action_type="clearance",
        near_expiry_product_id=product_id,
        store_id=store_id,
        assignee_id=store.manager_id,
        input_params=ClearanceParams(
            near_expiry_product_id=product_id,
            quantity=nep.stock_quantity,
            assignee_id=store.manager_id,
            target_discount=discount / 100.0,
        ),
        output_result={},
        status=TaskStatus.PENDING,
        actual_discount=discount / 100.0,
        quantity=nep.stock_quantity,
        created_at=datetime.now(),
    )
    ontology.create_clearance_task(task)

    return (
        f"✅ 出清任务已创建！\n"
        f"任务ID: {task.id}\n"
        f"门店: {store.name}({store_id})\n"
        f"商品: {product_id}\n"
        f"折扣: {discount}%\n"
        f"数量: {nep.stock_quantity}"
    )


@tool
def get_store_summary(store_id: str = None) -> str:
    """获取门店摘要：门店信息、员工、临期商品、任务统计。"""
    from services.ontology_service import OntologyService
    from datetime import date

    if not store_id:
        return "请指定门店ID，如 store_001"

    ontology = OntologyService()
    store = ontology.get_store(store_id)
    if not store:
        return f"门店 {store_id} 不存在"

    region = ontology.get_region(store.region_id)
    employees = ontology.get_employees_by_store(store_id)
    near_expiry = ontology.get_near_expiry_products_by_store(store_id)
    tasks = ontology.get_clearance_tasks_by_store(store_id)
    today = date.today()

    lines = [
        f"📊 门店摘要: {store.name} ({store.id})",
        f"   地址: {store.address}",
        f"   区域: {region.name if region else store.region_id}",
        f"   店长ID: {store.manager_id}\n",
        f"👥 员工 ({len(employees)}人):",
    ]
    for emp in employees:
        lines.append(f"   - {emp.name} ({emp.id}) | {emp.role.value}")

    lines.append(f"\n📦 临期商品: {len(near_expiry)} 种")
    for nep in near_expiry:
        product = ontology.get_product(nep.product_id)
        name = product.name if product else nep.product_id
        days = (nep.expiry_date - today).days
        lines.append(f"   - {nep.id}: {name} | 库存{nep.stock_quantity} | {nep.expiry_date}({days}天)")

    pending_tasks = [t for t in tasks if t.status.value == 'pending']
    lines.append(f"\n📋 出清任务: {len(tasks)} 个 (待执行: {len(pending_tasks)})")
    return "\n".join(lines)


# ===== 绑定工具 =====
tools = [
    get_near_expiry_products,
    create_clearance_task,
    confirm_clearance_task,
    query_entity,
    traverse_relation,
    create_entity,            # ← 通用创建
    update_entity,            # ← 通用更新
    get_store_summary,
]
llm_with_tools = llm.bind_tools(tools)


# ============ Deep Agent Graph ============

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # add_messages：自动按 ID 去重


def chat_node(state: AgentState) -> AgentState:
    """聊天节点 — LLM with ontology-driven tools"""
    from langchain_core.messages import SystemMessage

    messages = state.get("messages", [])
    if not messages:
        return {**state, "messages": []}

    # 动态生成本体系统提示
    ontology_prompt = build_ontology_prompt()
    store_context = f"\n\n当前用户选择的门店ID是: store_001。\n\n可用工具：\n- query_entity / create_entity / update_entity → 增删改查任意实体\n- traverse_relation → 遍历实体关系\n- get_near_expiry_products / create_clearance_task / confirm_clearance_task / get_store_summary\n\n**关键规则：**\n- create_clearance_task 获取预览后，必须询问用户确认\n- 用户回复\"确认\"后，立即调用 confirm_clearance_task\n- 用户要求修改任务参数（折扣/数量等）时，直接调用 update_entity\n- 用中文回复。"

    full_messages = [
        SystemMessage(content=ontology_prompt + store_context)
    ] + list(messages)

    try:
        response = llm_with_tools.invoke(full_messages)
    except Exception as e:
        from langchain_core.messages import AIMessage
        # 打印 DeepSeek 详细错误
        err_detail = str(e)
        if hasattr(e, 'response'):
            try:
                err_detail = e.response.json()
            except:
                err_detail = str(e.response) if hasattr(e, 'response') else str(e)
        print(f"[ERROR] LLM调用失败: {type(e).__name__}", flush=True)
        print(f"[ERROR] 详情: {err_detail}", flush=True)
        print(f"[ERROR] 消息数: {len(full_messages)}, 总token估算: {sum(len(str(getattr(m,'content',''))) for m in full_messages)//4}", flush=True)
        error_msg = f"抱歉，AI 服务暂时不可用 ({type(e).__name__})。请稍后重试。"
        return {"messages": [AIMessage(content=error_msg)]}

    return {"messages": [response]}


def tool_node(state: AgentState) -> AgentState:
    """工具执行节点"""
    from langchain_core.messages import ToolMessage

    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    if last_message and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        tool_messages = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id", "")

            tool_func = {t.name: t for t in tools}.get(tool_name)
            if tool_func:
                try:
                    result = tool_func.invoke(tool_args)
                except Exception as e:
                    result = f"工具执行错误: {str(e)}"
            else:
                result = f"未知工具: {tool_name}"

            tool_messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tool_call_id
            ))

        return {"messages": tool_messages}
    return {"messages": []}


def should_continue(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return "end"
    last = messages[-1]

    # 防止无限工具循环：连续工具调用超过 3 次则强制返回
    recent_tool_count = sum(1 for m in messages[-10:] if type(m).__name__ == "ToolMessage")
    if recent_tool_count >= 3:
        return "end"

    if hasattr(last, 'tool_calls') and last.tool_calls:
        return "tools"
    if type(last).__name__ == "ToolMessage":
        return "chat"
    return "end"


# ===== 构建 Graph（简化版：对话式 HITL，无 interrupt） =====
graph = StateGraph(AgentState)
graph.add_node("chat", chat_node)
graph.add_node("tools", tool_node)
graph.set_entry_point("chat")
graph.add_conditional_edges("chat", should_continue, {"tools": "tools", "end": END})
graph.add_conditional_edges("tools", should_continue, {"chat": "chat", "end": END})
compiled_graph = graph.compile(checkpointer=MemorySaver())


# ============ FastAPI 应用 ============

app = FastAPI(
    title="门店临期商品管理 - 本体驱动 Agent",
    description="基于 CopilotKit + 本体语义 + LangGraph 的 AI 助手",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_langgraph_fastapi_endpoint(
    app=app,
    agent=LangGraphAGUIAgent(
        name="default",
        description="门店临期商品管理助手（本体驱动）",
        graph=compiled_graph,
    ),
    path="/api/copilotkit",
)

@app.get("/health")
async def health():
    return {"status": "healthy"}

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8123"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
