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

    @property
    def tenant_context(self) -> TenantContext:
        """该 workspace 的默认上下文（通配 org，总部视角）。"""
        return TenantContext(workspace_name=self.workspace_name, org_unit_id="*")


_instances: Dict[str, WorkspaceAgentInstance] = {}

_DEFAULT_WORKSPACE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "workspace", "customer_default")


def bootstrap_workspace(workspace_name: str) -> WorkspaceAgentInstance:
    """构建（或取缓存）某 workspace 的 Agent 运行时实例（架构 spec §3.3/§7）。

    若 workspace 有自己的 ontology/ 目录（ontocopy 后），从其 TTL/Action
    构建 registry（本体语义隔离）；否则回退 pack registry（customer_default 兼容）。
    """
    if workspace_name in _instances:
        return _instances[workspace_name]

    # 取 workspace 配置：注册表 → 加载文件 → 默认
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # agent/
    root = os.path.dirname(base)                                         # 项目根

    cfg = get_workspace(workspace_name)
    if cfg is None:
        if workspace_name == "customer_default":
            try:
                cfg = load_workspace_config(_DEFAULT_WORKSPACE_DIR)
            except Exception:
                cfg = WorkspaceConfig(workspace_name="customer_default", name="默认",
                                      storage_type="json_files",
                                      data_dir=os.path.join(base, "..", "workspace", "retail", "data"))
        else:
            raise KeyError(f"未注册的 workspace: {workspace_name}")

    # data_dir 可能是相对路径（如 workspace/retail/data），需解析为绝对路径
    raw_data_dir = cfg.data_dir or os.path.join(base, "..", "workspace", "retail", "data")
    data_dir = raw_data_dir if os.path.isabs(raw_data_dir) else os.path.join(root, raw_data_dir)

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
        registry = _build_registry_from_workspace_ontology(ontology_dir, data_dir)
    else:
        # 无 workspace ontology 目录时，从 pack registry 构建（customer_default 走此路径）
        from engine.pack import get_workspace_dir, domains_to_registry
        from engine.bootstrap import bootstrap
        bootstrap()
        ws = get_workspace_dir(cfg.source_pack or "retail")
        if ws:
            registry = domains_to_registry(ws, data_dir=data_dir)
        else:
            from engine.parser import EntityRegistry
            registry = EntityRegistry()

    from engine.repository import JSONFileRepository
    repo = JSONFileRepository(data_dir=data_dir, registry=registry)

    # 接通 executor：config 取该 workspace source_pack 的（第一个）价值链流程（spec §5.3）。
    # 解析链：WorkspaceConfig.source_pack → get_workspace_dir → ws.processes → processes[0]。
    # 多 process 按 process_name 精确选择留 v2（_get_executor(workspace, process)）。
    from engine.executor import ActionExecutor
    from engine.pack import get_workspace_dir
    process_config = None
    if cfg.source_pack:
        ws = get_workspace_dir(cfg.source_pack)
        if ws and ws.processes:
            process_config = ws.processes[0]
    executor = ActionExecutor(
        repository=repo, actions=registry.action_types,
        registry=registry, config=process_config)

    inst = WorkspaceAgentInstance(
        workspace_name=workspace_name, config=cfg,
        registry=registry, repository=repo, executor=executor)
    _instances[workspace_name] = inst
    return inst


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
