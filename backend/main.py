"""FastAPI 主入口 — 本体驱动 AI 门店助手

架构：
- 本体语义定义: ontology/store.ttl
- 本体解析器: ontology/parser.py → EntityRegistry
- 通用工具: ontology/tools.py (query_entity, create_entity, traverse_relation)
- Agent: Deep Agents (create_deep_agent) + LangGraphAgent (ag_ui_langgraph)
- 前端: CopilotKit v1.57.4 via AG-UI 协议
"""

import os
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
from langgraph.checkpoint.memory import MemorySaver

from deepagents import create_deep_agent
from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint

# ===== 导入本体驱动通用工具 =====
from ontology.tools import query_entity, traverse_relation, create_entity, update_entity, build_ontology_prompt, _registry

# ============ LLM 配置 ============

api_key = os.getenv("QWEN_API_KEY")
if not api_key:
    raise RuntimeError("QWEN_API_KEY 环境变量未设置")

base_url = os.getenv("QWEN_BASE_URL", "https://api.minimaxi.com/v1")
model_name = os.getenv("QWEN_MODEL", "MiniMax-M2.7-highspeed")

llm = ChatOpenAI(
    model=model_name,
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


# ===== 绑定工具列表 =====
tools = [
    get_near_expiry_products,
    create_clearance_task,
    confirm_clearance_task,
    query_entity,
    traverse_relation,
    create_entity,
    update_entity,
    get_store_summary,
]


# ============ Deep Agent Graph ============

# 动态生成本体系统提示（Deep Agents 在启动时设置一次）
ontology_prompt = build_ontology_prompt()
store_context = """
当前用户选择的门店ID是: store_001。

可用工具：
- query_entity / create_entity / update_entity → 增删改查任意实体
- traverse_relation → 遍历实体关系
- get_near_expiry_products / create_clearance_task / confirm_clearance_task / get_store_summary

**关键规则：**
- create_clearance_task 获取预览后，必须询问用户确认
- 用户回复"确认"后，立即调用 confirm_clearance_task
- 用户要求修改任务参数（折扣/数量等）时，直接调用 update_entity
- 用中文回复。
"""

system_prompt = ontology_prompt + store_context

# 创建 Deep Agent Graph
# - SummarizationMiddleware 默认开启，自动压缩长对话上下文（解决 BadRequestError）
# - DeltaChannel 内置，checkpoint 增长从 O(N²) 降到 O(N)
# - checkpointer=MemorySaver 保持多轮会话状态
deep_agent_graph = create_deep_agent(
    model=llm,
    tools=tools,
    system_prompt=system_prompt,
    checkpointer=MemorySaver(),
    # 排除 Deep Agents 内置的通用工具（文件系统、shell、子agent），只保留业务工具
    # 通过 HarnessProfile 注册 excluded_tools
)


# ============ FastAPI 应用 ============

app = FastAPI(
    title="门店临期商品管理 - 本体驱动 Agent",
    description="基于 CopilotKit + 本体语义 + Deep Agents 的 AI 助手",
    version="0.3.0",
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
    agent=LangGraphAgent(
        name="default",
        description="门店临期商品管理助手（本体驱动 + Deep Agents）",
        graph=deep_agent_graph,
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
