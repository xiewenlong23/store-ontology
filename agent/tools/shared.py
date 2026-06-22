"""系统 Tool 的共享基础设施（依赖装配层）。

这些 helper 是 @tool 函数与 engine 之间的薄封装层：
- _parser / _get_repo / _get_executor：经 bootstrap_workspace 装配（spec §5.3 决策2）。
  默认（无参）路径从 main.tenant_ctx contextvar 解析 workspace_name；
  测试用 monkeypatch 替换整个 helper。
- _preview_cache：execute_action/confirm_action 的预览缓存
- build_ontology_prompt：为本体注入 system prompt
- _wrap：工具返回值的统一包装格式（summary + COPILOTKIT_DATA）
- _tc：从工具参数构造 TenantContext

系统 Tool（query/crud/action）与 workspace 业务 Tool 都依赖这些 helper。
"""
import json
import os
import warnings

from engine.repository import JSONFileRepository
from engine.executor import ActionExecutor
from engine.preview_cache import PreviewCache
from engine.tenant import TenantContext
from engine.workspace_bootstrap import bootstrap_workspace


# ============ 依赖装配（经 bootstrap_workspace；测试用 monkeypatch 替换）============

_preview_cache = PreviewCache(ttl_seconds=300)


def _warn_deprecated_vertical(vertical):
    """vertical= 参数已废弃（spec §5.3）；传非 None 值时警告，避免静默回归。"""
    if vertical is not None:
        warnings.warn(
            "_get_executor/_get_repo/_parser/build_ontology_prompt 的 vertical= 参数"
            "已废弃并被忽略；workspace 由 contextvar 解析，价值链流程用 process_name= 选。",
            DeprecationWarning,
            stacklevel=3)


def _workspace_name_from_ctx() -> str:
    """从 main.tenant_ctx contextvar 取当前请求的 workspace_name（默认 jjy）。

    request 中间件在处理请求时设置 tenant_ctx（TenantContext）。@tool 函数运行在请求
    线程内，故能读到。无 ctx（离线/测试）时回退 customer_default。
    """
    try:
        import main
        tc = main.tenant_ctx.get()
        return tc.workspace_name
    except (ImportError, LookupError):
        return "jjy"


def _parser(vertical: str = None):
    """获取 parser（带 registry）。

    vertical 已废弃（保留签名仅为 monkeypatch 向后兼容，spec §5.3）；忽略之，
    一律从 contextvar 解析 workspace 经 bootstrap_workspace 装配。
    """
    _warn_deprecated_vertical(vertical)
    inst = bootstrap_workspace(_workspace_name_from_ctx())

    class _P:
        registry = inst.registry
        data_dir = inst.repository.data_dir
        config = inst.config
        def build_system_prompt(self, intro):
            from engine.parser import OntologyParser
            return OntologyParser(ttl_path=None, data_dir=str(self.data_dir)).build_system_prompt(intro)
    return _P()


def _get_repo(tenant=None, vertical: str = None) -> JSONFileRepository:
    """取 Repository。tenant 是 TenantContext（携带 workspace_name）。

    vertical 已废弃（保留签名仅为 monkeypatch 向后兼容）；忽略之。
    无 tenant 时从 contextvar 解析 workspace。"""
    _warn_deprecated_vertical(vertical)
    if tenant is not None:
        return bootstrap_workspace(tenant.workspace_name).repository
    return bootstrap_workspace(_workspace_name_from_ctx()).repository


def _get_executor(vertical: str = None, process_name: str = None) -> ActionExecutor:
    """取 executor（经 bootstrap_workspace 装配，spec §5.3 决策2）。

    vertical 已废弃（保留仅为向后兼容，将被忽略）；改用 process_name 精确选价值链流程。
    默认从 contextvar 解析 workspace，返回该 workspace 缓存实例的 executor。
    process_name 匹配不到时回退默认 executor（processes[0]）并警告——避免静默错误。
    """
    _warn_deprecated_vertical(vertical)
    workspace_name = _workspace_name_from_ctx()
    inst = bootstrap_workspace(workspace_name)
    if process_name is None:
        return inst.executor
    # 精确匹配 process：从 source_pack 的 processes 取
    from engine.pack import get_workspace_dir
    ws = get_workspace_dir(inst.config.source_pack) if inst.config and inst.config.source_pack else None
    if ws is None:
        warnings.warn(f"workspace '{workspace_name}' 无 source_pack，忽略 process_name='{process_name}'",
                      stacklevel=2)
        return inst.executor
    for proc in ws.processes:
        if proc.name == process_name:
            return ActionExecutor(
                repository=inst.repository, actions=inst.registry.action_types,
                registry=inst.registry, config=proc)
    warnings.warn(
        f"process_name='{process_name}' 在工作目录 '{ws.name}' 的 processes "
        f"{[p.name for p in ws.processes]} 中未找到，回退默认 executor。",
        stacklevel=2)
    return inst.executor


def build_ontology_prompt(vertical: str = None) -> str:
    """为本体注入 system prompt。vertical 已废弃，忽略。"""
    _warn_deprecated_vertical(vertical)
    p = _parser()
    intro = ""
    from engine.pack import get_workspace_dir
    inst = bootstrap_workspace(_workspace_name_from_ctx())
    ws = get_workspace_dir(inst.config.source_pack) if inst.config and inst.config.source_pack else None
    if ws and ws.processes:
        intro = ws.processes[0].system_prompt_intro
    return p.build_system_prompt(intro)


def _wrap(data: dict, summary: str) -> str:
    return f"{summary}\n<!--COPILOTKIT_DATA-->\n{json.dumps(data, ensure_ascii=False)}\n<!--/COPILOTKIT_DATA-->"


def _tc(workspace_name: str, org_unit_id: str) -> TenantContext:
    """从工具参数构造 TenantContext。"""
    return TenantContext(workspace_name=workspace_name, org_unit_id=org_unit_id)


def _tc_ctx(workspace_name: str = None, org_unit_id: str = None) -> TenantContext:
    """构造 TenantContext：从请求 contextvar 取默认值，显式参数覆盖（v2-tenant动态）。

    工具应优先用本函数取 TenantContext。workspace_name/org_unit_id 传 None（默认）
    时从 main.tenant_ctx contextvar 取（反映当前请求的 header 注入值）；显式传值则
    覆盖（保留 LLM/测试显式指定租户的能力）。无 contextvar（离线/测试）回退默认。
    """
    try:
        import main
        base = main.tenant_ctx.get()
    except (ImportError, LookupError):
        base = TenantContext.default()
    return TenantContext(
        workspace_name=workspace_name if workspace_name is not None else base.workspace_name,
        org_unit_id=org_unit_id if org_unit_id is not None else base.org_unit_id,
    )


# ============ v2 信任修复（WP6）============

# 兜底角色：未认证或 Employee 关联缺失时用此 role（PermissionEvaluator 会按此
# 求值，多数业务资源的 read_roles 不含它 → 自动拒绝）。
_ANONYMOUS_ROLE = "anonymous"


def _get_actor(tenant=None) -> dict:
    """从 auth_ctx contextvar 派生可信 actor（设计文档 §5 WP6）。

    流程：auth_ctx.user_id → 查 workspace 的 Employee.user_id → 取 role。
    - 已登录且 Employee 关联存在 → actor={"role": <role>, "user_id": <uid>}
    - 已登录但无 Employee 关联 → actor={"role": "system_admin", "user_id": <uid>}
      （user 存在但无 employee 视为系统账号，至少能 query；具体资源由 TTL 再校验）
    - 未登录（auth_ctx anonymous）+ AUTH_REQUIRED=false → 兜底 system_admin
      （开发/测试模式：保留旧测试行为，全 allow；生产强制 auth 时此分支不可达）
    - 未登录 + AUTH_REQUIRED=true → actor={"role": "anonymous"}
    - 无 contextvar（离线）→ 兜底 actor={"role": "system_admin"}

    tenant: 显式 TenantContext（默认从 tenant_ctx contextvar 取）。
    """
    try:
        import main
        auth = main.auth_ctx.get()
    except (ImportError, LookupError, AttributeError):
        auth = None

    # 无 contextvar（测试环境）兜底——保持旧测试行为（全 allow）
    if auth is None:
        return {"role": "system_admin"}

    if not auth.is_authenticated():
        # AUTH_REQUIRED=false（开发/测试）→ 兜底 admin；生产强制 auth 不可达此分支
        if os.getenv("AUTH_REQUIRED", "true").lower() in ("false", "0", "no", "off"):
            return {"role": "system_admin"}
        return {"role": _ANONYMOUS_ROLE}

    # 已登录：查 Employee 关联推导 role
    ws_name = _workspace_name_from_ctx()
    try:
        from engine.identity import get_employee_by_user
        emp = get_employee_by_user(ws_name, auth.user_id)
        if emp and emp.get("role"):
            return {"role": emp["role"], "user_id": auth.user_id}
    except Exception:  # noqa: BLE001
        pass
    # Employee 无关联但已认证 → 系统账号（如 admin）
    return {"role": "system_admin", "user_id": auth.user_id}
