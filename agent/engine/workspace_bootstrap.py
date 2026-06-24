"""按 workspace 构建隔离的 Agent 运行时上下文（架构 spec §3.3）。

每个 workspace 独立的 OntologyRegistry + Repository，按 workspace_name 缓存。
两个 workspace 的实例互不干扰（数据隔离 + 本体语义隔离）。
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional

from engine.workspace import get_workspace, load_workspace_config, WorkspaceConfig
from engine.tenant import TenantContext


@dataclass
class WorkspaceAgentInstance:
    """一个 workspace 的 Agent 运行时实例（registry + repository + executor）。"""
    workspace_name: str
    config: WorkspaceConfig
    registry: object  # EntityRegistry
    repository: object  # Repository
    executor: object  # ActionExecutor（config 取自 source_pack 的价值链流程）
    log_repo: object = None  # ActionLogRepository（spec §4.1）；None 表示未启用 Action Log

    @property
    def tenant_context(self) -> TenantContext:
        """该 workspace 的默认上下文（通配 org，总部视角）。"""
        return TenantContext(workspace_name=self.workspace_name, org_unit_id="*")


_instances: Dict[str, WorkspaceAgentInstance] = {}

_DEFAULT_WORKSPACE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "workspace", "jjy")


def bootstrap_workspace(workspace_name: str) -> WorkspaceAgentInstance:
    """构建（或取缓存）某 workspace 的 Agent 运行时实例（架构 spec §3.3/§7）。

    若 workspace 有自己的 ontology/ 目录（ontocopy 后），从其 TTL/Action
    构建 registry（本体语义隔离）；否则回退 pack registry（jjy 兼容）。
    """
    if workspace_name in _instances:
        return _instances[workspace_name]

    # 取 workspace 配置：注册表 → 加载文件 → 默认
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # agent/
    root = os.path.dirname(base)                                         # 项目根

    cfg = get_workspace(workspace_name)
    if cfg is None:
        if workspace_name == "jjy":
            try:
                cfg = load_workspace_config(_DEFAULT_WORKSPACE_DIR)
            except Exception:
                cfg = WorkspaceConfig(workspace_name="jjy", name="默认",
                                      storage_type="json_files",
                                      data_dir=os.path.join(base, "..", "workspace", "retail", "data"))
        else:
            # v2 兜底 1：尝试从 WorkspaceDef 注册表（新模型）构造 WorkspaceConfig
            # retail/customerA 等用 workspace.py 注册的 workspace 走此路径
            from engine.pack import get_workspace_dir
            ws_def = get_workspace_dir(workspace_name)
            if ws_def is not None:
                cfg = WorkspaceConfig(
                    workspace_name=ws_def.name, name=ws_def.display_name,
                    storage_type="json_files",
                    data_dir=ws_def.data_dir or "",
                    ontology_dir=os.path.join(os.path.dirname(ws_def.data_dir or ""), "ontology")
                        if ws_def.data_dir else "",
                )
            else:
                # v2 兜底 2：历史/未知 workspace 名（如 customer_default / customer_id 旧值）
                # 视为默认 jjy workspace（向后兼容，避免 LLM 传错 workspace 名直接崩）
                # 实际数据过滤仍由 Repository.matches 的 workspace_name 比较保证隔离。
                try:
                    cfg = load_workspace_config(_DEFAULT_WORKSPACE_DIR)
                    # 覆盖 workspace_name 为请求值（让上下文一致）
                    cfg.workspace_name = workspace_name
                except Exception:
                    cfg = WorkspaceConfig(
                        workspace_name=workspace_name, name=workspace_name,
                        storage_type="json_files",
                        data_dir=os.path.join(base, "..", "workspace", "jjy", "data"))

    # data_dir 可能是相对路径（如 workspace/retail/data），需解析为绝对路径
    raw_data_dir = cfg.data_dir or os.path.join(base, "..", "workspace", "retail", "data")
    data_dir = raw_data_dir if os.path.isabs(raw_data_dir) else os.path.join(root, raw_data_dir)

    # ----- v2-存储：优先用 PG；PG 不可用回落 JSON 文件 -----
    from engine.db import is_pg_enabled, ping, PGNotConfigured
    use_pg = is_pg_enabled() and ping()

    if use_pg:
        try:
            from engine import pg_ontology_repo
            registry = pg_ontology_repo.load_registry(workspace_name)
        except (PGNotConfigured, Exception) as e:  # noqa: BLE001
            # PG 加载失败 → 回落 JSON 路径
            print(f"[bootstrap] PG load_registry 失败，回落 JSON：{e}")
            use_pg = False
            registry = _load_registry_from_files(cfg, data_dir, workspace_name, base, root)
    else:
        registry = _load_registry_from_files(cfg, data_dir, workspace_name, base, root)

    # 选 Repository 实现（PG 或 JSON）
    if use_pg:
        from engine.pg_data_repo import PgDataRepository
        repo = PgDataRepository(workspace_name=workspace_name, registry=registry)
    else:
        from engine.repository import JSONFileRepository
        repo = JSONFileRepository(data_dir=data_dir, registry=registry)

    # 接通 executor：config 取该工作目录的（第一个）价值链流程。
    # 解析链：优先 source_pack；否则用 workspace_name 本身（自洽工作目录以自己名字注册）。
    from engine.executor import ActionExecutor
    from engine.pack import get_workspace_dir
    process_config = None
    # 自洽工作目录（如 jjy）以自己名字注册为 workspace_dir；旧式薄壳用 source_pack
    ws_name_for_dir = cfg.source_pack or workspace_name
    ws = get_workspace_dir(ws_name_for_dir)
    if ws and ws.processes:
        process_config = ws.processes[0]
    executor = ActionExecutor(
        repository=repo, actions=registry.action_types,
        registry=registry, config=process_config)

    # Action Log repo（spec §4.1）：PG 或 JSON 双后端；构造失败不应阻断 workspace 启动
    log_repo = None
    try:
        from engine.action_log_repo import build_action_log_repo
        log_repo = build_action_log_repo(workspace_name=workspace_name, data_dir=data_dir)
        executor.log_repo = log_repo
    except Exception as e:  # noqa: BLE001
        print(f"[bootstrap] action_log_repo 构造失败（日志将不写入）: {e}")
    if log_repo is None:
        # 操作员可见的失效信号（spec §12.4 运维可观测性；M5 review 建议）
        print(f"[bootstrap] ⚠️ workspace '{workspace_name}' 未启用 Action Log（log_repo=None）")

    inst = WorkspaceAgentInstance(
        workspace_name=workspace_name, config=cfg,
        registry=registry, repository=repo, executor=executor, log_repo=log_repo)
    _instances[workspace_name] = inst
    return inst


def _load_registry_from_files(cfg, data_dir: str, workspace_name: str,
                               base: str, root: str):
    """回落路径：从 TTL/YAML 文件构建 registry（原 bootstrap_workspace 的逻辑）。"""
    # I-3: 优先用 cfg.ontology_dir（显式声明）；回退：从 data_dir 推导（兼容旧 config）
    ontology_dir = cfg.ontology_dir
    if not ontology_dir and cfg.data_dir:
        ontology_dir = os.path.join(os.path.dirname(cfg.data_dir), "ontology")

    # ontology_dir 可能是相对路径（如 "ontology"），需解析为绝对路径（相对 workspace_root）
    if ontology_dir and not os.path.isabs(ontology_dir):
        workspace_root = os.path.dirname(data_dir)
        ontology_dir = os.path.join(workspace_root, ontology_dir)

    if ontology_dir and os.path.isdir(os.path.join(ontology_dir, "domains")):
        # 从 workspace 自定义 ontology 构建（本体语义隔离）
        return _build_registry_from_workspace_ontology(ontology_dir, data_dir)
    else:
        # 无 workspace ontology 目录时，从 pack registry 构建（jjy 走此路径）
        from engine.pack import get_workspace_dir, domains_to_registry
        from engine.bootstrap import bootstrap
        bootstrap()
        ws = get_workspace_dir(cfg.source_pack or "retail")
        if ws:
            return domains_to_registry(ws, data_dir=data_dir)
        from engine.parser import EntityRegistry
        return EntityRegistry()


def _build_registry_from_workspace_ontology(ontology_dir: str, data_dir: str):
    """从 workspace 的 ontology/ 目录构建 EntityRegistry（架构 spec §3.3）。

    扫描 ontology/domains/*/domain.ttl 解析 Object/Link，
    扫描 ontology/domains/*/actions/*.yaml + ontology/processes/*/actions/*.yaml 加载 Action。
    """
    from engine.parser import OntologyParser, EntityRegistry
    from engine.action_loader import load_actions

    registry = EntityRegistry()

    # domains TTL
    domains_dir = os.path.join(ontology_dir, "domains")
    if os.path.isdir(domains_dir):
        for domain_name in os.listdir(domains_dir):
            ttl = os.path.join(domains_dir, domain_name, "domain.ttl")
            if os.path.exists(ttl):
                p = OntologyParser(ttl_path=ttl, data_dir=data_dir)
                registry.object_types.update(p.registry.object_types)
                registry.link_types.update(p.registry.link_types)
            # domain actions
            actions = os.path.join(domains_dir, domain_name, "actions")
            if os.path.isdir(actions):
                registry.action_types.update(load_actions(actions))

    # process actions
    processes_dir = os.path.join(ontology_dir, "processes")
    if os.path.isdir(processes_dir):
        for proc_name in os.listdir(processes_dir):
            actions = os.path.join(processes_dir, proc_name, "actions")
            if os.path.isdir(actions):
                registry.action_types.update(load_actions(actions))

    return registry


def get_workspace_agent_instance(workspace_name: str) -> Optional[WorkspaceAgentInstance]:
    return _instances.get(workspace_name)


def reset_instances() -> None:
    """测试用：清空全部实例缓存。"""
    _instances.clear()


def invalidate_workspace(workspace_name: str) -> None:
    """失效单个 workspace 的缓存实例（本体编辑后调用，I-2 修复）。"""
    _instances.pop(workspace_name, None)
