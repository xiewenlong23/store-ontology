"""客户配置（P1）：CustomerConfig + OrgUnit 树 + 客户注册表。

每个客户（企业）一份 CustomerConfig，声明启用的域/流程、存储、OrgUnit 树。
"""
import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class OrgUnit:
    """组织单元（Brand > Region > Store 的节点）。"""
    id: str
    parent: Optional[str] = None  # None = 根节点

    class Tree:
        """OrgUnit 树，支持祖先链/子孙集/可见范围查询。"""
        def __init__(self, units: List["OrgUnit"]):
            self._by_id = {u.id: u for u in units}
            self._children: Dict[str, List[str]] = {}
            for u in units:
                self._children.setdefault(u.parent or "__root__", []).append(u.id)

        def ancestors(self, unit_id: str) -> List[str]:
            """从自身往上的祖先链（含自身）。"""
            chain = [unit_id]
            cur = self._by_id.get(unit_id)
            while cur and cur.parent:
                chain.append(cur.parent)
                cur = self._by_id.get(cur.parent)
            return chain

        def descendants(self, unit_id: str) -> List[str]:
            """从自身往下的子孙集（含自身）。"""
            result = [unit_id]
            for child_id in self._children.get(unit_id, []):
                result.extend(self.descendants(child_id))
            return result

        def visible_units(self, unit_id: str) -> set:
            """某 OrgUnit 用户可见的单元集 = 自身 + 所有子孙。"""
            return set(self.descendants(unit_id))

    @classmethod
    def from_dict(cls, d: dict) -> "OrgUnit":
        return cls(id=d["id"], parent=d.get("parent"))


@dataclass
class CustomerConfig:
    """单个客户的配置。"""
    customer_id: str
    name: str
    source_pack: str = ""
    storage_type: str = "json_files"  # MVP: json_files; v2: postgres
    data_dir: str = ""
    ontology_dir: str = ""  # I-3: 显式声明（不再从 data_dir 推导）
    enabled_domains: List[str] = field(default_factory=list)
    enabled_processes: List[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    org_units: List[OrgUnit] = field(default_factory=list)

    @property
    def org_tree(self) -> Optional[OrgUnit.Tree]:
        if not self.org_units:
            return None
        return OrgUnit.Tree(self.org_units)


# ============ 客户注册表 ============

_registry: Dict[str, CustomerConfig] = {}


def register_customer(config: CustomerConfig) -> None:
    _registry[config.customer_id] = config


def get_customer(customer_id: str) -> Optional[CustomerConfig]:
    return _registry.get(customer_id)


def all_customers() -> List[CustomerConfig]:
    return list(_registry.values())


def clear_customers() -> None:
    _registry.clear()


def load_customer_config(customer_dir: str) -> CustomerConfig:
    """从 customers/<id>/config.yaml 加载客户配置。"""
    config_path = os.path.join(customer_dir, "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    units = [OrgUnit.from_dict(u) for u in data.get("org_tree", [])]
    return CustomerConfig(
        customer_id=data["customer_id"],
        name=data.get("name", data["customer_id"]),
        source_pack=data.get("source_pack", ""),
        storage_type=data.get("storage", {}).get("type", "json_files"),
        data_dir=data.get("storage", {}).get("data_dir", ""),
        ontology_dir=data.get("ontology_dir", ""),  # I-3: 显式读
        enabled_domains=data.get("enabled_domains", []),
        enabled_processes=data.get("enabled_processes", []),
        parameters=data.get("parameters", {}),
        org_units=units,
    )
