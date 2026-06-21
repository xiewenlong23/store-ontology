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
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# sys.path 需同时含 agent/（让 `from engine...` 可导入）和项目根（让 `from agent.tools...` 可导入）。
# 这样无论从 agent/ 还是项目根执行 `python main.py` 都能正确解析。
sys.path.insert(0, os.path.dirname(__file__))   # agent/
sys.path.insert(0, _PROJECT_ROOT)               # 项目根
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=True)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint

# ===== 内核通用工具（与行业包无关）=====
from agent.tools import (
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
    from engine.pack import all_workspace_dirs
    collected = []
    for ws in all_workspace_dirs():
        for proc in ws.processes:
            if not proc.tools_module:
                continue
            try:
                mod = importlib.import_module(proc.tools_module)
                collected.extend(getattr(mod, "TOOLS", []))
            except Exception as e:  # noqa: BLE001
                print(f"[main] 加载 pack '{ws.name}' process '{proc.name}' 工具失败: {e}")
    return collected


def _aggregate_skill_paths():
    """聚合各 pack process 的 skill 挂载路径。只收录含 SKILL.md 的目录。"""
    paths = []
    from engine.pack import all_workspace_dirs
    for ws in all_workspace_dirs():
        for proc in ws.processes:
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


def _list_system_skill_dirs():
    """扫描 agent/skills/ 下的系统级 Skill 目录（含 SKILL.md）。

    系统 Skill 对所有 workspace 通用（平台能力），优先级低于 workspace Skill。
    架构 spec §3.2：2 级 Skill 加载（workspace > 系统）。
    """
    sys_skills_root = os.path.join(os.path.dirname(__file__), "skills")
    dirs = []
    if os.path.isdir(sys_skills_root):
        for name in os.listdir(sys_skills_root):
            if name in ("tmp", "__pycache__") or name.startswith("."):
                continue
            skill_path = os.path.join(sys_skills_root, name)
            if os.path.isdir(skill_path) and os.path.exists(
                    os.path.join(skill_path, "SKILL.md")):
                dirs.append(name)
    return dirs


def _build_combined_prompt() -> str:
    """合并所有工作目录的本体提示。"""
    from engine.pack import all_workspace_dirs, domains_to_registry
    from engine.parser import OntologyParser
    parts = []
    for ws in all_workspace_dirs():
        for proc in ws.processes:
            intro = proc.system_prompt_intro or ws.display_name
            registry = domains_to_registry(ws, data_dir=ws.data_dir or ".")
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


# ============ 工具清单（内核固定）===========
_KERNEL_TOOLS = [
    query_entity,
    create_entity,
    update_entity,
    traverse_relation,
    execute_action,
    confirm_action,
    query_task,
    update_task,
]

_STORE_CONTEXT = """
当前客户上下文由请求 header X-Workspace + X-Org-Unit-ID 注入。

**操作流程（Preview → Confirm）：**
1. 用户要求执行业务操作时，先 execute_action 获取预览（返回 preview_id）
2. 展示预览，询问确认
3. 用户确认后，confirm_action(preview_id) 执行
4. 受治理的写操作是一条工作流（各 Action 的合法状态迁移见对应 Skill），状态机只允许相邻迁移
5. 用中文回复
"""


# ============ per-workspace agent 构建 + 缓存 ============

import contextvars
from engine.tenant import TenantContext

tenant_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "tenant_ctx", default=TenantContext.default())


def _build_ws_tools(ws_name: str):
    """聚合指定工作目录的工具（内核 + 该目录的 process.tools_module）。"""
    import importlib
    from engine.pack import get_workspace_dir
    ws = get_workspace_dir(ws_name)
    collected = list(_KERNEL_TOOLS)
    if ws:
        for proc in ws.processes:
            if not proc.tools_module:
                continue
            try:
                mod = importlib.import_module(proc.tools_module)
                collected.extend(getattr(mod, "TOOLS", []))
            except Exception as e:  # noqa: BLE001
                print(f"[main] 加载工作目录 '{ws_name}' process '{proc.name}' 工具失败: {e}")
    # 去重
    seen = set()
    tools = []
    for t in collected:
        n = getattr(t, "name", "")
        if n in seen:
            continue
        seen.add(n)
        tools.append(t)
    return tools


def _build_ws_prompt(ws_name: str) -> str:
    """构建指定工作目录的本体提示（只含该目录的实体/关系/Action）。"""
    from engine.pack import get_workspace_dir, domains_to_registry
    ws = get_workspace_dir(ws_name)
    if not ws:
        return _STORE_CONTEXT
    parts = []
    registry = domains_to_registry(ws, data_dir=ws.data_dir or ".")
    for proc in ws.processes:
        intro = proc.system_prompt_intro or ws.display_name
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
    ontology = "\n\n---\n\n".join(parts) if parts else ""
    return ontology + "\n\n" + _STORE_CONTEXT


def _build_ws_skills(ws_name: str):
    """构建指定工作目录的 skill 路径 + skills backend。"""
    from engine.pack import get_workspace_dir
    ws = get_workspace_dir(ws_name)
    ws_skill_paths = []
    if ws:
        for proc in ws.processes:
            if not proc.skills_dir or not os.path.isdir(proc.skills_dir):
                continue
            for name in os.listdir(proc.skills_dir):
                if name in ("tmp", "__pycache__"):
                    continue
                skill_path = os.path.join(proc.skills_dir, name)
                if os.path.isdir(skill_path) and os.path.exists(
                        os.path.join(skill_path, "SKILL.md")):
                    ws_skill_paths.append(f"/{name}/")

    sys_skill_names = _list_system_skill_dirs()
    skill_paths = [f"/system/{n}/" for n in sys_skill_names] + (ws_skill_paths or ["/store-ontology/"])

    # skills backend：workspace skills（根路径）+ 系统 skills（/system/ 路由）
    ws_skills_root = None
    if ws and ws.processes:
        ws_skills_root = ws.processes[0].skills_dir
    if ws_skills_root and os.path.isdir(ws_skills_root):
        ws_backend = FilesystemBackend(root_dir=ws_skills_root, virtual_mode=True)
    else:
        ws_backend = FilesystemBackend(
            root_dir=os.path.join(os.path.dirname(__file__), "skills"), virtual_mode=True)

    from deepagents.backends.composite import CompositeBackend
    if sys_skill_names:
        sys_backend = FilesystemBackend(
            root_dir=os.path.join(os.path.dirname(__file__), "skills"), virtual_mode=True)
        backend = CompositeBackend(default=ws_backend, routes={"/system/": sys_backend})
    else:
        backend = ws_backend
    return skill_paths, backend


def build_workspace_graph(ws_name: str):
    """构建指定工作目录的 deep agent graph（per-workspace 隔离）。"""
    tools = _build_ws_tools(ws_name)
    prompt = _build_ws_prompt(ws_name)
    skill_paths, backend = _build_ws_skills(ws_name)
    return create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=prompt,
        checkpointer=MemorySaver(),
        backend=backend,
        skills=skill_paths,
    )


from ag_ui_langgraph import LangGraphAgent
_ws_agents: dict = {}


def get_or_build_ws_agent(ws_name: str) -> LangGraphAgent:
    """per-workspace agent 缓存。graph 按工作目录隔离。"""
    if ws_name not in _ws_agents:
        graph = build_workspace_graph(ws_name)
        _ws_agents[ws_name] = LangGraphAgent(name=ws_name, graph=graph)
    return _ws_agents[ws_name]


# ============ FastAPI 应用 ============

_pack_names = ", ".join(p.name for p in __import__('engine.pack', fromlist=['all_workspace_dirs']).all_workspace_dirs()) or "无"
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
    """从 X-Workspace（架构 §3.4，优先）+ X-Org-Unit-ID header 解析，注入 TenantContext contextvar。

    TenantContext.from_headers 内部兼容 X-Workspace 优先、X-Customer-ID 回退（旧前端）。
    """
    tc = TenantContext.from_headers({
        "X-Workspace": request.headers.get("X-Workspace"),
        "X-Customer-ID": request.headers.get("X-Customer-ID"),
        "X-Org-Unit-ID": request.headers.get("X-Org-Unit-ID"),
    })
    token = tenant_ctx.set(tc)
    try:
        return await call_next(request)
    finally:
        tenant_ctx.reset(token)


@app.middleware("http")
async def workspace_middleware(request, call_next):
    """解析 X-Workspace header，注入 request.state.workspace_name（架构 spec §3.4）。

    前端通过 X-Workspace header 告诉后端运行在哪个 workspace 上。
    未传时默认 customer_default（保持向后兼容）。
    具体 workspace 运行时上下文的构建（bootstrap_workspace）在各路由内按需调用，
    通过 _resolve_workspace_name(request) 统一取值（header 优先，URL {cid} 回退）。
    """
    ws = request.headers.get("X-Workspace") or "jjy"
    request.state.workspace_name = ws
    return await call_next(request)


def _resolve_workspace_name(request, url_cid: str = None) -> str:
    """统一解析当前请求的 workspace 标识（架构 spec §3.4）。

    优先级：X-Workspace header > URL {cid} 参数 > 默认 customer_default。
    URL {cid} 回退保证旧前端调用（admin/dashboard 路由）仍可用。
    """
    ws = getattr(request.state, "workspace_name", None)
    if ws:
        return ws
    if url_cid:
        return url_cid
    return "jjy"


# ============ AG-UI 网关 endpoint（per-workspace agent 路由）============
from ag_ui.core.types import RunAgentInput
from ag_ui.encoder import EventEncoder
from fastapi.responses import StreamingResponse


@app.post("/api/copilotkit")
async def copilotkit_endpoint(input_data: RunAgentInput, request: Request):
    """AG-UI 网关：按 X-Workspace 路由到 per-workspace agent 实例。

    每个工作目录有独立 agent（工具/skill/本体隔离）。
    """
    ws_name = _resolve_workspace_name(request)
    agent = get_or_build_ws_agent(ws_name)
    request_agent = agent.clone()  # per-request 状态隔离
    accept_header = request.headers.get("accept")
    encoder = EventEncoder(accept=accept_header)

    async def event_generator():
        async for event in request_agent.run(input_data):
            yield encoder.encode(event)
    return StreamingResponse(event_generator(), media_type=encoder.get_content_type())


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ============ 本体管理 API（P4 §4.5，只读浏览）============

from engine.workspace_bootstrap import bootstrap_workspace


@app.get("/api/admin/customers/{cid}/ontology/objects")
async def admin_ontology_objects(request: Request, cid: str):
    """该客户所有 Object Type 定义（只读浏览）。"""
    inst = bootstrap_workspace(_resolve_workspace_name(request, cid))
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
async def admin_ontology_actions(request: Request, cid: str):
    """该客户所有 Action Type 定义。"""
    inst = bootstrap_workspace(_resolve_workspace_name(request, cid))
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
async def admin_ontology_links(request: Request, cid: str):
    """该客户所有 Link Type 定义。"""
    inst = bootstrap_workspace(_resolve_workspace_name(request, cid))
    links = []
    for lt in inst.registry.link_types.values():
        links.append({
            "id": lt.id, "label": lt.label, "label_zh": lt.label_zh,
            "domain": lt.domain, "range": lt.range, "via": lt.via,
        })
    return {"links": links}


# ============ 运营看板 API（P4 §4.4）============

@app.get("/api/dashboard/{cid}/metrics")
async def dashboard_metrics(request: Request, cid: str):
    """跨域 KPI 指标卡。"""
    inst = bootstrap_workspace(_resolve_workspace_name(request, cid))
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
async def dashboard_todos(request: Request, cid: str):
    """待办列表：非终态的 Task（需人介入）。"""
    inst = bootstrap_workspace(_resolve_workspace_name(request, cid))
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
    """启动时注册各行业包的定时 job 并启动 scheduler。"""
    try:
        from workspace.retail.skills.clearance_workflow.automation import register_clearance_automation
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
    from agent.tools.shared import _get_executor
    from workspace.retail.skills.clearance_workflow.automation import handle_approval
    ex = _get_executor(process_name="clearance")
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
    from agent.tools.shared import _get_executor
    from workspace.retail.skills.clearance_workflow.automation import handle_pos_scan
    ex = _get_executor(process_name="clearance")
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
