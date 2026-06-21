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

from engine.parser import get_ontology_parser
from engine.repository import JSONFileRepository
from engine.executor import ActionExecutor
from engine.preview_cache import PreviewCache
from engine.tenant import TenantContext
from engine.workspace_bootstrap import bootstrap_workspace


# ============ 依赖装配（经 bootstrap_workspace；测试用 monkeypatch 替换）============

_preview_cache = PreviewCache(ttl_seconds=300)


def _workspace_name_from_ctx() -> str:
    """从 main.tenant_ctx contextvar 取当前请求的 workspace_name（默认 customer_default）。

    request 中间件在处理请求时设置 tenant_ctx（TenantContext）。@tool 函数运行在请求
    线程内，故能读到。无 ctx（离线/测试）时回退 customer_default。
    """
    try:
        import main
        tc = main.tenant_ctx.get()
        return tc.workspace_name
    except (ImportError, LookupError):
        return "customer_default"


def _parser(vertical: str = None):
    """获取 parser（带 registry）。

    vertical 已废弃（保留签名仅为 monkeypatch 向后兼容，spec §5.3）；忽略之，
    一律从 contextvar 解析 workspace 经 bootstrap_workspace 装配。
    """
    del vertical  # 废弃参数，忽略
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
    del vertical
    if tenant is not None:
        return bootstrap_workspace(tenant.workspace_name).repository
    return bootstrap_workspace(_workspace_name_from_ctx()).repository


def _get_executor(vertical: str = None, process_name: str = None) -> ActionExecutor:
    """取 executor（经 bootstrap_workspace 装配，spec §5.3 决策2）。

    vertical 已废弃（保留仅为向后兼容，将被忽略）；改用 process_name 精确选价值链流程。
    默认从 contextvar 解析 workspace，返回该 workspace 缓存实例的 executor。
    """
    del vertical
    workspace_name = _workspace_name_from_ctx()
    inst = bootstrap_workspace(workspace_name)
    if process_name is None:
        return inst.executor
    # 精确匹配 process：从 source_pack 的 processes 取
    from engine.pack import get_pack
    pack = get_pack(inst.config.source_pack) if inst.config and inst.config.source_pack else None
    if pack is None:
        return inst.executor
    for proc in pack.processes:
        if proc.name == process_name:
            return ActionExecutor(
                repository=inst.repository, actions=inst.registry.action_types,
                registry=inst.registry, config=proc)
    return inst.executor


def build_ontology_prompt(vertical: str = None) -> str:
    """为本体注入 system prompt。vertical 已废弃，忽略。"""
    del vertical
    p = _parser()
    intro = ""
    from engine.pack import get_pack
    inst = bootstrap_workspace(_workspace_name_from_ctx())
    pack = get_pack(inst.config.source_pack) if inst.config and inst.config.source_pack else None
    if pack and pack.processes:
        intro = pack.processes[0].system_prompt_intro
    return p.build_system_prompt(intro)


def _wrap(data: dict, summary: str) -> str:
    return f"{summary}\n<!--COPILOTKIT_DATA-->\n{json.dumps(data, ensure_ascii=False)}\n<!--/COPILOTKIT_DATA-->"


def _tc(workspace_name: str, org_unit_id: str) -> TenantContext:
    """从工具参数构造 TenantContext。"""
    return TenantContext(workspace_name=workspace_name, org_unit_id=org_unit_id)
