"""按客户构建隔离的 Agent 实例（P1）。

每个客户独立的 OntologyRegistry + Repository，按 customer_id 缓存。
两个客户的实例互不干扰（数据隔离 + 本体语义隔离）。
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional

from ontology.customer import get_customer, load_customer_config, CustomerConfig
from ontology.tenant import TenantContext


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
    "..", "data", "customers", "customer_default")


def bootstrap_customer(customer_id: str) -> CustomerAgentInstance:
    """构建（或取缓存）某客户的 Agent 实例。"""
    if customer_id in _instances:
        return _instances[customer_id]

    # 取客户配置：注册表 → 加载文件 → 默认
    cfg = get_customer(customer_id)
    if cfg is None:
        if customer_id == "customer_default":
            try:
                cfg = load_customer_config(_DEFAULT_CUSTOMER_DIR)
            except Exception:
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                root = os.path.dirname(base)
                cfg = CustomerConfig(customer_id="customer_default", name="默认",
                                     storage_type="json_files",
                                     data_dir=os.path.join(root, "data"))
        else:
            raise KeyError(f"未注册的客户: {customer_id}")

    # 构建 registry（复用现有 parser，指向客户数据目录）
    from ontology.parser import OntologyParser
    from ontology.repository import JSONFileRepository
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.dirname(base)
    ttl_path = os.path.join(base, "ontology", "store.ttl")
    data_dir = cfg.data_dir or os.path.join(root, "data")
    parser = OntologyParser(ttl_path=ttl_path, data_dir=data_dir)
    # 加载 actions
    from ontology.action_loader import load_actions
    actions_dir = os.path.join(base, "ontology", "actions")
    if os.path.isdir(actions_dir):
        parser.registry.action_types = load_actions(actions_dir)
    repo = JSONFileRepository(data_dir=data_dir, registry=parser.registry)

    inst = CustomerAgentInstance(
        customer_id=customer_id, config=cfg,
        registry=parser.registry, repository=repo, executor=None)
    _instances[customer_id] = inst
    return inst


def get_customer_agent_instance(customer_id: str) -> Optional[CustomerAgentInstance]:
    return _instances.get(customer_id)


def reset_instances() -> None:
    """测试用：清空实例缓存。"""
    _instances.clear()
