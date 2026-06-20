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

# 从项目根目录的 .env 读取配置（不再使用 backend/.env）
# override=True：让 .env 文件值优先于进程已有的同名环境变量（避免 shell 残留旧配置干扰）
sys.path.insert(0, os.path.dirname(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint

# ===== 内核通用工具（与 vertical 无关）=====
from engine.tools import (
    query_entity, create_entity, update_entity, traverse_relation,
    execute_action, confirm_action, query_task, update_task,
    build_ontology_prompt,
)

# ===== bootstrap（自动发现 packs/*/pack.py）=====
from engine.bootstrap import bootstrap as _bootstrap

_bootstrap()


def _aggregate_pack_tools():
    """从各 pack 的 process.tools_module 聚合专属工具。"""
    import importlib
    from engine.pack import all_packs
    collected = []
    for pack in all_packs():
        for proc in pack.processes:
            if not proc.tools_module:
                continue
            try:
                mod = importlib.import_module(proc.tools_module)
                collected.extend(getattr(mod, "TOOLS", []))
            except Exception as e:  # noqa: BLE001
                print(f"[main] 加载 pack '{pack.name}' process '{proc.name}' 工具失败: {e}")
    return collected


def _aggregate_skill_paths():
    """聚合各 pack process 的 skill 挂载路径。只收录含 SKILL.md 的目录。"""
    paths = []
    from engine.pack import all_packs
    for pack in all_packs():
        for proc in pack.processes:
            if not proc.skills_dir or not os.path.isdir(proc.skills_dir):
                continue
            for name in os.listdir(proc.skills_dir):
                if name in ("tmp", "__pycache__"):
                    continue
                skill_path = os.path.join(proc.skills_dir, name)
                if os.path.isdir(skill_path) and os.path.exists(
                        os.path.join(skill_path, "SKILL.md")):
                    paths.append(f"/{name}/")
    return paths


def _build_combined_prompt() -> str:
    """合并所有 pack 的本体提示。"""
    from engine.pack import all_packs, pack_to_registry
    from engine.parser import OntologyParser
    parts = []
    for pack in all_packs():
        for proc in pack.processes:
            intro = proc.system_prompt_intro or pack.display_name
            registry = pack_to_registry(pack, data_dir=pack.data_dir or ".")
            # 用 parser 的 build_system_prompt 格式化
            p = type('P', (), {'registry': registry})()
            lines = [f"{intro}\n"]
            lines.append("可用实体（用 query_entity 查询）: "
                         + ", ".join(ot.label_zh for ot in registry.object_types.values()))
            lines.append("\n关系（用 traverse_relation）: "
                         + ", ".join(f"{lt.label_zh}({lt.domain}->{lt.range})"
                                     for lt in registry.link_types.values()))
            lines.append("\n操作（用 execute_action/confirm_action）: "
                         + ", ".join(registry.action_types.keys()))
            lines.append("\n用中文回复。")
            parts.append("\n".join(lines))
    return "\n\n---\n\n".join(parts) if parts else ""


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


# ============ 工具清单（内核固定 + vertical 聚合）===========
_all_tools = [
    query_entity,
    create_entity,
    update_entity,
    traverse_relation,
    execute_action,
    confirm_action,
    query_task,
    update_task,
] + _aggregate_pack_tools()

# 去重：同名工具只保留第一个（vertical 与 pack 共存期避免冲突）
_seen = set()
tools = []
for _t in _all_tools:
    _n = getattr(_t, "name", "")
    if _n in _seen:
        continue
    _seen.add(_n)
    tools.append(_t)


# ============ Deep Agent Graph ============

import contextvars
from engine.tenant import TenantContext

# 客户租户上下文：由 HTTP middleware（X-Customer-ID + X-Org-Unit-ID header）注入
tenant_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "tenant_ctx", default=TenantContext.default())

# 动态生成本体系统提示（从 pack registry 构建，不依赖单 TTL parser）
ontology_prompt = _build_combined_prompt()
store_context = """
当前客户上下文由请求 header X-Customer-ID + X-Org-Unit-ID 注入（默认 customer_default + 全部门店）。

**操作流程（Preview → Confirm）：**
1. 用户要求执行业务操作时，先 execute_action 获取预览（返回 preview_id）
2. 展示预览，询问确认
3. 用户确认后，confirm_action(preview_id) 执行
4. 受治理的写操作是一条工作流（各 Action 的合法状态迁移见对应 Skill），状态机只允许相邻迁移
5. 用中文回复
"""

system_prompt = ontology_prompt + store_context

# Skill 源路径（FilesystemBackend 从磁盘加载）；root 指向 pack process skills
_clearance_skills_root = os.path.join(os.path.dirname(__file__),
    "packs", "retail", "processes", "clearance", "skills")
skills_backend = FilesystemBackend(root_dir=_clearance_skills_root, virtual_mode=True)

# 创建 Deep Agent Graph
# - SummarizationMiddleware 默认开启，自动压缩长对话上下文（解决 BadRequestError）
# - DeltaChannel 内置，checkpoint 增长从 O(N²) 降到 O(N)
# - SkillsMiddleware 从所有 vertical 的 skills/ 加载 SKILL.md（Progressive Disclosure）
# - checkpointer=MemorySaver 保持多轮会话状态
_skill_paths = _aggregate_skill_paths() or ["/store-ontology/"]
deep_agent_graph = create_deep_agent(
    model=llm,
    tools=tools,
    system_prompt=system_prompt,
    checkpointer=MemorySaver(),
    backend=skills_backend,
    skills=_skill_paths,
    # 排除 Deep Agents 内置的通用工具（文件系统、shell、子agent），只保留业务工具
)


# ============ FastAPI 应用 ============

_pack_names = ", ".join(p.name for p in __import__('engine.pack', fromlist=['all_packs']).all_packs()) or "无"
app = FastAPI(
    title="OntologyAgent APaaS - 本体驱动 Agent",
    description=f"基于 CopilotKit + 本体语义 + Deep Agents 的 AI 助手（已加载 pack: {_pack_names}）",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def tenant_middleware(request, call_next):
    """从 X-Customer-ID + X-Org-Unit-ID header 解析，注入 TenantContext contextvar。"""
    tc = TenantContext.from_headers({
        "X-Customer-ID": request.headers.get("X-Customer-ID"),
        "X-Org-Unit-ID": request.headers.get("X-Org-Unit-ID"),
    })
    token = tenant_ctx.set(tc)
    try:
        return await call_next(request)
    finally:
        tenant_ctx.reset(token)


add_langgraph_fastapi_endpoint(
    app=app,
    agent=LangGraphAgent(
        name="default",
        description="本体驱动业务助手（多 vertical + Deep Agents）",
        graph=deep_agent_graph,
    ),
    path="/api/copilotkit",
)


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ============ 本体管理 API（P4 §4.5，只读浏览）============

from engine.customer_bootstrap import bootstrap_customer


@app.get("/api/admin/customers/{cid}/ontology/objects")
async def admin_ontology_objects(cid: str):
    """该客户所有 Object Type 定义（只读浏览）。"""
    inst = bootstrap_customer(cid)
    objects = []
    for ot in inst.registry.object_types.values():
        objects.append({
            "id": ot.id, "label": ot.label, "label_zh": ot.label_zh,
            "comment": ot.comment, "storage_file": ot.storage_file,
            "status": ot.status, "edits_only_via_actions": ot.edits_only_via_actions,
            "properties": [{"name": p.name, "type": p.type} for p in ot.properties],
        })
    return {"objects": objects}


@app.get("/api/admin/customers/{cid}/ontology/actions")
async def admin_ontology_actions(cid: str):
    """该客户所有 Action Type 定义。"""
    inst = bootstrap_customer(cid)
    actions = []
    for at in inst.registry.action_types.values():
        actions.append({
            "api_name": at.api_name, "display_name": at.display_name,
            "description": at.description, "target_object_type": at.target_object_type,
            "edits_object_types": at.edits_object_types,
            "parameters": at.parameters, "locator_field": at.locator_field,
        })
    return {"actions": actions}


@app.get("/api/admin/customers/{cid}/ontology/links")
async def admin_ontology_links(cid: str):
    """该客户所有 Link Type 定义。"""
    inst = bootstrap_customer(cid)
    links = []
    for lt in inst.registry.link_types.values():
        links.append({
            "id": lt.id, "label": lt.label, "label_zh": lt.label_zh,
            "domain": lt.domain, "range": lt.range, "via": lt.via,
        })
    return {"links": links}


# ============ 运营看板 API（P4 §4.4）============

@app.get("/api/dashboard/{cid}/metrics")
async def dashboard_metrics(cid: str):
    """跨域 KPI 指标卡。"""
    inst = bootstrap_customer(cid)
    tc = inst.tenant_context

    # Task 按 status 分组计数
    tasks = inst.repository.read("Task", tc)
    task_counts = {}
    for t in tasks:
        s = t.get("status", "unknown")
        task_counts[s] = task_counts.get(s, 0) + 1

    # NearExpiryProduct 按 status 分组计数
    neps = inst.repository.read("NearExpiryProduct", tc)
    nep_counts = {}
    for n in neps:
        s = n.get("status", "unknown")
        nep_counts[s] = nep_counts.get(s, 0) + 1

    return {
        "tasks": {"total": len(tasks), "by_status": task_counts},
        "near_expiry": {"total": len(neps), "by_status": nep_counts},
    }


@app.get("/api/dashboard/{cid}/todos")
async def dashboard_todos(cid: str):
    """待办列表：非终态的 Task（需人介入）。"""
    inst = bootstrap_customer(cid)
    tc = inst.tenant_context
    tasks = inst.repository.read("Task", tc)
    active_statuses = {"created", "pending_approval", "approved", "accepted", "in_progress"}
    todos = [t for t in tasks if t.get("status") in active_statuses]
    return {"todos": todos}


# ============ 后端自动化：scheduler 生命周期 + webhook 路由 ============

from engine.scheduler import AutomationScheduler

_automation_scheduler = AutomationScheduler()


@app.on_event("startup")
async def _start_automation():
    """启动时注册各 vertical 的定时 job 并启动 scheduler。"""
    try:
        from packs.retail.processes.clearance.automation import register_clearance_automation
        register_clearance_automation(_automation_scheduler, interval_seconds=1800)
    except Exception as e:  # noqa: BLE001
        print(f"[startup] 注册 clearance 自动化失败: {e}")
    _automation_scheduler.start()


@app.on_event("shutdown")
async def _stop_automation():
    _automation_scheduler.shutdown()


@app.post("/api/webhooks/approval")
async def webhook_approval(body: dict):
    """审批回调（模拟端点）→ approve_clearance。

    body: {task_id, approver_id, approved: bool}
    真实审批系统集成留 v2。
    """
    from engine.tools import _get_executor
    from packs.retail.processes.clearance.automation import handle_approval
    ex = _get_executor(vertical="clearance")
    try:
        result = handle_approval(ex, task_id=body["task_id"],
                                 approver_id=body["approver_id"],
                                 approved=body.get("approved", True))
        return result
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


@app.post("/api/webhooks/pos")
async def webhook_pos(body: dict):
    """POS 扫码事件（模拟端点）→ deduct_stock。

    body: {target_id, task_id, quantity}
    真实 POS 系统集成留 v2。
    """
    from engine.tools import _get_executor
    from packs.retail.processes.clearance.automation import handle_pos_scan
    ex = _get_executor(vertical="clearance")
    try:
        result = handle_pos_scan(ex, target_id=body["target_id"],
                                 task_id=body["task_id"], quantity=body["quantity"])
        return result
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8123"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
