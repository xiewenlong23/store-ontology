"""按客户构建隔离的 Agent 实例（P1）。

每个客户独立的 OntologyRegistry + Repository，按 customer_id 缓存。
两个客户的实例互不干扰（数据隔离 + 本体语义隔离）。
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional

from engine.customer import get_customer, load_customer_config, CustomerConfig
from engine.tenant import TenantContext


@dataclass
class CustomerAgentInstance:
    """一个客户的 Agent 运行时实例（registry + repository + executor）。"""
    customer_id: str
    config: CustomerConfig
    registry: object  # EntityRegistry
    repository: object  # Repository
    executor: object  # ActionExecutor（后续 task 构建；P1 先不接 executor）

    @property
    def tenant_context(self) -> TenantContext:
        """该客户的默认上下文（通配 org，总部视角）。"""
        return TenantContext(customer_id=self.customer_id, org_unit_id="*")


_instances: Dict[str, CustomerAgentInstance] = {}

_DEFAULT_CUSTOMER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "workspace", "customer_default")


def bootstrap_customer(customer_id: str) -> CustomerAgentInstance:
    """构建（或取缓存）某客户的 Agent 实例。

    P3 升级：若客户有自己的 ontology/ 目录（ontocopy 后），从客户的 TTL/Action
    构建 registry（本体语义隔离）；否则回退全局 store.ttl（customer_default 兼容）。
    """
    if customer_id in _instances:
        return _instances[customer_id]

    # 取客户配置：注册表 → 加载文件 → 默认
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # agent/
    root = os.path.dirname(base)                                         # 项目根

    cfg = get_customer(customer_id)
    if cfg is None:
        if customer_id == "customer_default":
            try:
                cfg = load_customer_config(_DEFAULT_CUSTOMER_DIR)
            except Exception:
                cfg = CustomerConfig(customer_id="customer_default", name="默认",
                                     storage_type="json_files",
                                     data_dir=os.path.join(base, "..", "workspace", "retail", "data"))
        else:
            raise KeyError(f"未注册的客户: {customer_id}")

    # data_dir 可能是相对路径（如 workspace/retail/data），需解析为绝对路径
    raw_data_dir = cfg.data_dir or os.path.join(base, "..", "workspace", "retail", "data")
    data_dir = raw_data_dir if os.path.isabs(raw_data_dir) else os.path.join(root, raw_data_dir)

    # I-3: 优先用 cfg.ontology_dir（显式声明）；回退：从 data_dir 推导（兼容旧 config）
    ontology_dir = cfg.ontology_dir
    if not ontology_dir and cfg.data_dir:
        ontology_dir = os.path.join(os.path.dirname(cfg.data_dir), "ontology")

    # ontology_dir 可能是相对路径（如 "ontology"），需解析为绝对路径（相对 customer_root）
    if ontology_dir and not os.path.isabs(ontology_dir):
        customer_root = os.path.dirname(data_dir)
        ontology_dir = os.path.join(customer_root, ontology_dir)

    if ontology_dir and os.path.isdir(os.path.join(ontology_dir, "domains")):
        # 从客户自定义 ontology 构建（本体语义隔离）
        registry = _build_registry_from_customer_ontology(ontology_dir, data_dir)
    else:
        # 无客户 ontology 目录时，从 pack registry 构建（customer_default 走此路径）
        from engine.pack import get_pack, pack_to_registry
        from engine.bootstrap import bootstrap
        bootstrap()
        pack = get_pack(cfg.source_pack or "retail")
        if pack:
            registry = pack_to_registry(pack, data_dir=data_dir)
        else:
            from engine.parser import EntityRegistry
            registry = EntityRegistry()

    from engine.repository import JSONFileRepository
    repo = JSONFileRepository(data_dir=data_dir, registry=registry)

    inst = CustomerAgentInstance(
        customer_id=customer_id, config=cfg,
        registry=registry, repository=repo, executor=None)
    _instances[customer_id] = inst
    return inst


def _build_registry_from_customer_ontology(ontology_dir: str, data_dir: str):
    """从客户的 ontology/ 目录构建 EntityRegistry（P3）。

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


def get_customer_agent_instance(customer_id: str) -> Optional[CustomerAgentInstance]:
    return _instances.get(customer_id)


def reset_instances() -> None:
    """测试用：清空全部实例缓存。"""
    _instances.clear()


def invalidate_customer(customer_id: str) -> None:
    """失效单个客户的缓存实例（本体编辑后调用，I-2 修复）。"""
    _instances.pop(customer_id, None)
