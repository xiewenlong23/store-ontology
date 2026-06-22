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
from ag_ui_langgraph import LangGraphAgent

# ===== 内核通用工具（与行业包无关）=====
from agent.tools import (
    query_entity, create_entity, update_entity, traverse_relation,
    execute_action, confirm_action, query_task, update_task,
    build_ontology_prompt,
)

# ===== bootstrap（自动发现 packs/*/pack.py）=====
from engine.bootstrap import bootstrap as _bootstrap

_bootstrap()

# ===== v2 认证：首次启动种入各 workspace 的初始 admin（幂等，设计文档 §5 WP1）=====
from engine.identity import seed_all_workspaces

seed_all_workspaces()


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


# ============ 工具清单（内核固定）=============


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
from engine.auth import AuthContext

tenant_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "tenant_ctx", default=TenantContext.default())

# v2 认证（设计文档 §5 WP2）：auth_ctx 承载当前请求的可信身份。
# WP2 阶段 auth_middleware 只注入 auth_ctx 不强制（无 token 也通过，返回 anonymous）；
# WP6 切换为强制——除豁免路径外，无 token → 401。
auth_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "auth_ctx", default=AuthContext.anonymous())


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
    未传时默认 jjy（保持向后兼容）。
    具体 workspace 运行时上下文的构建（bootstrap_workspace）在各路由内按需调用，
    通过 _resolve_workspace_name(request) 统一取值（header 优先，URL {cid} 回退）。
    """
    ws = request.headers.get("X-Workspace") or "jjy"
    request.state.workspace_name = ws
    return await call_next(request)


# ============ v2 认证 middleware（设计文档 §5 WP2/WP6）============
# WP6：默认强制认证（无 token/过期/跨 ws 越权 → 401）。
# 通过 AUTH_REQUIRED=false env 可关闭（测试/开发兜底；生产必须开启）。

_AUTH_EXEMPT_PATHS = {"/api/auth/login", "/health"}


def _auth_required() -> bool:
    """是否强制认证。env AUTH_REQUIRED=false 关闭（默认开启）。"""
    val = os.getenv("AUTH_REQUIRED", "true").strip().lower()
    return val not in ("false", "0", "no", "off")


@app.middleware("http")
async def auth_middleware(request, call_next):
    """解析 Authorization Bearer，校验 JWT 签名 → 注入 auth_ctx contextvar。

    WP6 强制模式（默认）：
    - 豁免路径（/api/auth/login、/health）放行
    - 其余路径无 token / token 无效 / token ws 白名单不含当前 X-Workspace → 401
    - env AUTH_REQUIRED=false 可关闭强制（开发/测试兜底）

    跨 ws 越权防护：token 声明的 ws 白名单不含当前 X-Workspace → 视为未授权。
    """
    from engine.auth import decode_token, TokenError, AuthContext
    from engine.auth_audit import log_auth_event
    from fastapi.responses import JSONResponse

    auth = AuthContext.anonymous()
    failure: tuple = None   # (reason, detail)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        try:
            payload = decode_token(token, expected_typ="access")
            ws_list = tuple(payload.get("ws", []))
            # 跨 ws 越权校验：X-Workspace 必须在 token ws 白名单内
            req_ws = request.headers.get("X-Workspace") or "jjy"
            if ws_list and req_ws not in ws_list:
                failure = ("token_invalid",
                           f"token 不含 workspace '{req_ws}'（ws 白名单：{list(ws_list)}）")
            else:
                auth = AuthContext(
                    user_id=payload.get("sub", ""),
                    session_id=payload.get("sid", ""),
                    workspace_names=ws_list,
                )
        except TokenError as e:
            failure = ("token_invalid", str(e))
    else:
        failure = ("token_missing", "缺少 Authorization Bearer header")

    if failure:
        event, detail = failure
        client_ip = request.client.host if request.client else None
        log_auth_event(event, outcome="failed", detail=detail, client_ip=client_ip)
        # 强制模式 + 非豁免路径 → 401
        if _auth_required() and request.url.path not in _AUTH_EXEMPT_PATHS:
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权", "reason": detail})

    token_set = auth_ctx.set(auth)
    try:
        return await call_next(request)
    finally:
        auth_ctx.reset(token_set)


def _resolve_workspace_name(request, url_cid: str = None) -> str:
    """统一解析当前请求的 workspace 标识（架构 spec §3.4）。

    优先级：X-Workspace header > URL {cid} 参数 > 默认 jjy。
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


# ============ v2 认证 endpoints（设计文档 §5 WP2）============
# 4 个端点：login / refresh / me / logout
# 身份数据存 workspace（设计文档 §1 边界），agent 层只做编排 + JWT 签发。

from pydantic import BaseModel as _BM, Field as _Field


class LoginRequest(_BM):
    username: str = _Field(..., description="实名（工号/手机号），跨 workspace 一致")
    password: str


class RefreshRequest(_BM):
    refresh_token: str


@app.post("/api/auth/login")
async def auth_login(req: LoginRequest, request: Request):
    """登录：扫描所有 workspace 验证 → 签发 JWT。

    设计文档 §2.2：username 实名一致，password_hash 各 workspace 独立；
    返回 memberships（认成功的 workspace 列表）+ access/refresh token。
    """
    from engine.identity import list_user_workspaces
    from engine.auth import issue_session_tokens
    from engine.auth_audit import log_auth_event

    client_ip = request.client.host if request.client else None
    memberships = list_user_workspaces(req.username, req.password)
    if not memberships:
        log_auth_event("login", username=req.username, outcome="failed",
                       detail="无匹配 workspace 或密码错", client_ip=client_ip)
        return {"success": False, "error": "用户名或密码错误"}

    ws_names = [m["workspace_name"] for m in memberships]
    user_id = memberships[0]["user_id"]
    tokens = issue_session_tokens(user_id=user_id, workspace_names=ws_names)
    log_auth_event("login", username=req.username, user_id=user_id,
                   outcome="success", detail=f"workspaces={ws_names}", client_ip=client_ip)
    return {
        "success": True,
        "token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "session_id": tokens["session_id"],
        "expires_in": tokens["expires_in"],
        "memberships": memberships,
    }


@app.post("/api/auth/refresh")
async def auth_refresh(req: RefreshRequest, request: Request):
    """用 refresh token 换新的 access token。

    refresh token 不含 ws 白名单；需重新调 list_user_workspaces 重新求值
    （因为 workspace 列表可能变化）。MVP 简化：用原 token 的 sub（user_id）
    作为 username 索引无效——refresh 流程要求 client 重新登录（WP2 简化）。
    """
    from engine.auth import decode_token, TokenError, issue_session_tokens
    from engine.auth_audit import log_auth_event

    client_ip = request.client.host if request.client else None
    try:
        payload = decode_token(req.refresh_token, expected_typ="refresh")
    except TokenError as e:
        log_auth_event("refresh", outcome="failed", detail=str(e), client_ip=client_ip)
        return {"success": False, "error": f"refresh token 无效: {e}"}
    # MVP：refresh 仅返回新的 access token（同 user + session），ws 白名单沿用原 token。
    # 完整实现（重新求值 memberships）留 v2.1。
    from engine.auth import create_access_token
    user_id = payload.get("sub", "")
    session_id = payload.get("sid", "")
    # ws 白名单不在 refresh token 里——这里无法恢复，返回 401 要求重新登录。
    log_auth_event("refresh", user_id=user_id, outcome="failed",
                   detail="MVP 不支持 refresh，请重新 login", client_ip=client_ip)
    return {"success": False, "error": "MVP 阶段请重新登录（refresh 完整支持留 v2.1）"}


@app.get("/api/auth/me")
async def auth_me(request: Request):
    """返回当前认证身份 + memberships + visible_tools（设计文档 §5 WP7 前端用）。

    可信身份来自 auth_ctx contextvar（auth_middleware 注入）。
    visible_tools 由 PermissionEvaluator 求值：列出当前 role 可用的工具。
    """
    auth = auth_ctx.get()
    if not auth.is_authenticated():
        return {"authenticated": False}

    # 求当前 role 的可见工具清单
    visible_tools = []
    try:
        from agent.tools.shared import _get_actor, _get_evaluator
        actor = _get_actor()
        evaluator = _get_evaluator()
        role = actor.get("role", "")
        # 内核 8 工具 + 该 workspace 的专属工具
        from agent.tools import (
            query_entity, create_entity, update_entity, traverse_relation,
            execute_action, confirm_action, query_task, update_task)
        kernel_tools = [query_entity, create_entity, update_entity, traverse_relation,
                        execute_action, confirm_action, query_task, update_task]
        for t in kernel_tools:
            name = getattr(t, "name", "")
            if name and evaluator.can_use_tool(role, name).granted:
                visible_tools.append(name)
        # workspace 专属工具
        from engine.pack import get_workspace_dir
        import importlib
        ws = get_workspace_dir(_resolve_workspace_name(request))
        if ws:
            for proc in ws.processes:
                if not proc.tools_module:
                    continue
                try:
                    mod = importlib.import_module(proc.tools_module)
                    for t in getattr(mod, "TOOLS", []):
                        name = getattr(t, "name", "")
                        if name and evaluator.can_use_tool(role, name).granted:
                            visible_tools.append(name)
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001
        pass

    return {
        "authenticated": True,
        "user_id": auth.user_id,
        "session_id": auth.session_id,
        "workspace_names": list(auth.workspace_names),
        "visible_tools": visible_tools,
    }


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    """登出（MVP：客户端清 token；服务端 token 撤销列表留 v2.1）。"""
    from engine.auth_audit import log_auth_event
    auth = auth_ctx.get()
    client_ip = request.client.host if request.client else None
    log_auth_event("logout", user_id=auth.user_id or None,
                   outcome="success", client_ip=client_ip)
    return {"success": True, "detail": "客户端请清除本地 token"}


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


# ============ v2 本体 CRUD 写端点（WP7 + WP8 失效，spec §3/§4）============

from fastapi.responses import JSONResponse
from engine.admin_ontology_api import (
    json_to_object_type, json_to_link_type, json_to_action_def,
    require_admin,
)
from engine.workspace_bootstrap import invalidate_workspace
from engine import pg_ontology_repo as _ont_repo


def _ontology_to_dict(ot) -> dict:
    """ObjectType → dict（与 list_object_types 输出对称，用于响应 body）。"""
    return {
        "id": ot.id, "label": ot.label, "label_zh": ot.label_zh,
        "comment": ot.comment, "storage_file": ot.storage_file,
        "status": ot.status, "visibility": ot.visibility,
        "edits_only_via_actions": ot.edits_only_via_actions,
        "read_roles": ot.read_roles, "read_except": ot.read_except,
        "write_roles": ot.write_roles, "write_except": ot.write_except,
        "properties": [{"name": p.name, "type": p.type,
                        "read_roles": p.read_roles, "read_except": p.read_except,
                        "write_roles": p.write_roles, "write_except": p.write_except}
                       for p in ot.properties],
    }


def _link_to_dict(lt) -> dict:
    return {
        "id": lt.id, "label": lt.label, "label_zh": lt.label_zh,
        "comment": lt.comment, "domain": lt.domain, "range": lt.range,
        "via": lt.via, "use_roles": lt.use_roles, "use_except": lt.use_except,
    }


def _action_to_dict(ad) -> dict:
    return {
        "api_name": ad.api_name, "display_name": ad.display_name,
        "description": ad.description, "status": ad.status,
        "target_object_type": ad.target_object_type,
        "edits_object_types": list(ad.edits_object_types or []),
        "locator_field": ad.locator_field,
        "parameters": list(ad.parameters or []),
        "submission_criteria": dict(ad.submission_criteria or {}),
        "side_effects": list(ad.side_effects or []),
    }


# ----- Object Types -----

@app.post("/api/admin/customers/{cid}/ontology/objects")
async def admin_create_object(request: Request, cid: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    try:
        ot = json_to_object_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_object_type(ws_name, ot)
    invalidate_workspace(ws_name)
    return {"created": _ontology_to_dict(ot)}


@app.put("/api/admin/customers/{cid}/ontology/objects/{name}")
async def admin_update_object(request: Request, cid: str, name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    body["id"] = name  # 路径主键覆盖 body（spec §3.1）
    try:
        ot = json_to_object_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_object_type(ws_name, ot)
    invalidate_workspace(ws_name)
    return {"updated": _ontology_to_dict(ot)}


@app.delete("/api/admin/customers/{cid}/ontology/objects/{name}")
async def admin_delete_object(request: Request, cid: str, name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    ok = _ont_repo.delete_object_type(ws_name, name)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": f"{name} 不存在"})
    invalidate_workspace(ws_name)
    return {"deleted": True}


# ----- Link Types -----

@app.post("/api/admin/customers/{cid}/ontology/links")
async def admin_create_link(request: Request, cid: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    try:
        lt = json_to_link_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_link_type(ws_name, lt)
    invalidate_workspace(ws_name)
    return {"created": _link_to_dict(lt)}


@app.put("/api/admin/customers/{cid}/ontology/links/{name}")
async def admin_update_link(request: Request, cid: str, name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    body["id"] = name
    try:
        lt = json_to_link_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_link_type(ws_name, lt)
    invalidate_workspace(ws_name)
    return {"updated": _link_to_dict(lt)}


@app.delete("/api/admin/customers/{cid}/ontology/links/{name}")
async def admin_delete_link(request: Request, cid: str, name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    ok = _ont_repo.delete_link_type(ws_name, name)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": f"{name} 不存在"})
    invalidate_workspace(ws_name)
    return {"deleted": True}


# ----- Action Types -----

@app.post("/api/admin/customers/{cid}/ontology/actions")
async def admin_create_action(request: Request, cid: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    try:
        ad = json_to_action_def(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_action_type(ws_name, ad)
    invalidate_workspace(ws_name)
    return {"created": _action_to_dict(ad)}


@app.put("/api/admin/customers/{cid}/ontology/actions/{api_name}")
async def admin_update_action(request: Request, cid: str, api_name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    body["api_name"] = api_name
    try:
        ad = json_to_action_def(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_action_type(ws_name, ad)
    invalidate_workspace(ws_name)
    return {"updated": _action_to_dict(ad)}


@app.delete("/api/admin/customers/{cid}/ontology/actions/{api_name}")
async def admin_delete_action(request: Request, cid: str, api_name: str):
    ws_name = _resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    ok = _ont_repo.delete_action_type(ws_name, api_name)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": f"{api_name} 不存在"})
    invalidate_workspace(ws_name)
    return {"deleted": True}


# ============ v2 管理数据浏览 API（WP7 配套）============

@app.get("/api/admin/customers/{cid}/data/{entity_type}")
async def admin_data_browse(request: Request, cid: str, entity_type: str):
    """管理员数据浏览（只读）：列出指定 entity_type 的全部记录。

    用途：admin UI 展示 User/Role/PermissionGrant/OrgUnit/Category 等数据。
    权限：需要 system_admin 角色（PermissionEvaluator 校验）。其他角色 → 403。

    entity_type 限制为 identity/organization/category/personnel 域的"管理类"对象，
    避免业务数据（Task/NearExpiryProduct 等）泄露（那些走各自的工具）。
    """
    inst = bootstrap_workspace(_resolve_workspace_name(request, cid))
    ws_name = _resolve_workspace_name(request, cid)
    # v2 权限：管理数据浏览允许 system_admin 或 username=='admin'（初始管理员），
    # 走统一 require_admin；非 admin 但 PermissionEvaluator 允许 read 的角色仍放行（保留旧语义）。
    from agent.tools.shared import _get_actor as _ga, _get_evaluator
    from fastapi.responses import JSONResponse
    denied = require_admin(ws_name)
    if denied:
        actor = _ga()
        role = actor.get("role", "")
        evaluator = _get_evaluator()
        if not evaluator.can_read_object(role, entity_type).granted:
            return denied
    # 总部视角读全部（admin 数据不应受 org_unit 隔离）
    tc = TenantContext(workspace_name=_resolve_workspace_name(request, cid), org_unit_id="*")
    rows = inst.repository.read(entity_type, tc)
    # 脱敏：User 表剥离 password_hash
    if entity_type == "User":
        rows = [{k: v for k, v in r.items() if k != "password_hash"} for r in rows]
    return {"entity_type": entity_type, "total": len(rows), "items": rows}


# ============ 运营看板 API（P4 §4.4）============

@app.get("/api/dashboard/{cid}/metrics")
async def dashboard_metrics(request: Request, cid: str):
    """跨域 KPI 指标卡。"""
    inst = bootstrap_workspace(_resolve_workspace_name(request, cid))
    # v2（WP6）：用请求级 tenant_ctx（反映 X-Org-Unit-ID header），
    # 不再用 inst.tenant_context（硬编码 org_unit_id="*" 的总部视角，越权）。
    tc = tenant_ctx.get()

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
    tc = tenant_ctx.get()   # v2（WP6）：请求级，非 inst.tenant_context
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
