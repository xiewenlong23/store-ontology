"""Workspace 配置（架构 spec §3.3）：WorkspaceConfig + OrgUnit 树 + workspace 注册表。

每个 workspace（行业包模板或客户实例）一份 WorkspaceConfig，声明启用的域/流程、存储、OrgUnit 树。
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
class WorkspaceConfig:
    """单个 workspace 的配置。"""
    workspace_name: str
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


# ============ workspace 注册表 ============

_registry: Dict[str, WorkspaceConfig] = {}


def register_workspace(config: WorkspaceConfig) -> None:
    _registry[config.workspace_name] = config


def get_workspace(workspace_name: str) -> Optional[WorkspaceConfig]:
    return _registry.get(workspace_name)


def all_workspaces() -> List[WorkspaceConfig]:
    return list(_registry.values())


def clear_workspaces() -> None:
    _registry.clear()


def load_workspace_config(workspace_dir: str) -> WorkspaceConfig:
    """从 workspace/<name>/config.yaml 加载 workspace 配置。

    兼容旧格式：YAML 中若无 workspace_name 字段，回退读 customer_id（数据迁移期）。
    """
    config_path = os.path.join(workspace_dir, "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    units = [OrgUnit.from_dict(u) for u in data.get("org_tree", [])]
    ws_name = data.get("workspace_name") or data.get("customer_id")  # 兼容旧 YAML
    return WorkspaceConfig(
        workspace_name=ws_name,
        name=data.get("name", ws_name),
        source_pack=data.get("source_pack", ""),
        storage_type=data.get("storage", {}).get("type", "json_files"),
        data_dir=data.get("storage", {}).get("data_dir", ""),
        ontology_dir=data.get("ontology_dir", ""),  # I-3: 显式读
        enabled_domains=data.get("enabled_domains", []),
        enabled_processes=data.get("enabled_processes", []),
        parameters=data.get("parameters", {}),
        org_units=units,
    )
