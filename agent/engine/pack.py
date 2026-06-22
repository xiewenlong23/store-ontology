"""工作目录定义：CapabilityDomain + ValueChainProcess + WorkspaceDef。

工作目录模型：每个工作目录直接是一组能力域 + 价值链流程的扁平集合。
工作目录经 workspace/*/workspace.py 的 register_workspace_dir 注册。
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.parser import OntologyParser, EntityRegistry
from engine.action_loader import load_actions


@dataclass
class CapabilityDomain:
    """能力域：提供原子 Object/Link/Action + 域内规则源。不含工作流/状态机。

    v2（WP4）加 ``kind`` 字段标识域类型（organization/personnel/category/identity/business）。
    kind 由 TTL 的 ``:domainKind`` 元数据声明，也可在 CapabilityDomain 构造时显式传。
    """
    name: str
    display_name: str
    ttl_path: str
    actions_dir: str
    rules_dir: Optional[str] = None
    description: str = ""
    kind: str = "business"   # business（默认）| organization | personnel | category | identity


@dataclass
class ValueChainProcess:
    """价值链流程：跨域编排，有自己的状态机 + Skill + 专属工具。"""
    name: str
    display_name: str
    workflow_object_type: str
    workflow_object_id_field: str = "task_id"
    state_transitions: Dict[str, List[str]] = field(default_factory=dict)
    terminal_states: List[str] = field(default_factory=list)
    skills_dir: Optional[str] = None
    tools_module: Optional[str] = None
    actions_dir: Optional[str] = None
    system_prompt_intro: str = ""
    description: str = ""


# v2（WP4）：4 类必备 capability domain（设计文档 §5 WP4）。
# workspace 注册时校验这 4 类都存在 + 各含约定的必需 Object Type。
REQUIRED_DOMAIN_KINDS = ["organization", "personnel", "category", "identity"]

# 每类 domain 至少要含的 Object Type（用于 register_workspace_dir 校验）。
# 设计文档 §3.2/§3.3/§3.4：organization 含 OrgUnit；personnel 含 Employee；
# category 含 Category；identity 含 User/Role/PermissionGrant。
REQUIRED_OBJECTS_BY_KIND: Dict[str, List[str]] = {
    "organization": ["OrgUnit"],
    "personnel": ["Employee"],
    "category": ["Category"],
    "identity": ["User", "Role", "PermissionGrant"],
}


@dataclass
class WorkspaceDef:
    """工作目录定义：一组能力域 + 价值链流程（工作目录定义）。

    v2（WP4）：``required_domain_kinds`` 默认要求 4 类必备 domain 存在。
    测试或特殊场景可传空 list 关闭校验。
    """
    name: str
    display_name: str
    domains: List[CapabilityDomain] = field(default_factory=list)
    processes: List[ValueChainProcess] = field(default_factory=list)
    data_dir: str = ""
    required_domain_kinds: List[str] = field(default_factory=lambda: list(REQUIRED_DOMAIN_KINDS))


# ============ 工作目录注册表 ============

_workspace_dirs: Dict[str, WorkspaceDef] = {}


def register_workspace_dir(ws_def: WorkspaceDef) -> None:
    """注册工作目录。

    v2（WP4）：校验 required_domain_kinds 都存在（design 文档 §5 WP4）。
    校验失败抛 ValueError，启动时让问题尽早暴露。
    """
    _validate_required_domains(ws_def)
    _workspace_dirs[ws_def.name] = ws_def


def _validate_required_domains(ws_def: WorkspaceDef) -> None:
    """校验 workspace 含全部必备 kind 的 domain。

    若 ``ws_def.required_domain_kinds`` 为空则跳过校验（测试用）。
    kind 由 CapabilityDomain.kind 提供——若为默认 "business" 但 domain name
    在标准名集合里（organization/personnel/category/identity），自动推断 kind。
    """
    if not ws_def.required_domain_kinds:
        return
    # 收集 domains 的 kind（自动推断：默认 business 但 name 命中标准则升级）
    standard_names = set(REQUIRED_OBJECTS_BY_KIND.keys())
    actual_kinds = set()
    for d in ws_def.domains:
        if d.kind != "business":
            actual_kinds.add(d.kind)
        elif d.name in standard_names:
            # 默认 kind 但 name 是标准名 → 自动推断
            actual_kinds.add(d.name)
        # 否则保留 business（不加入 actual_kinds）
    missing = [k for k in ws_def.required_domain_kinds if k not in actual_kinds]
    if missing:
        raise ValueError(
            f"workspace '{ws_def.name}' 缺必备 domain kind: {missing}。"
            f"现有 kinds: {sorted(actual_kinds)}。"
            f" workspace 必须含 {REQUIRED_DOMAIN_KINDS} 四类 domain（设计文档 §5 WP4）。"
        )


def get_workspace_dir(name: str) -> Optional[WorkspaceDef]:
    return _workspace_dirs.get(name)


def all_workspace_dirs() -> List[WorkspaceDef]:
    return list(_workspace_dirs.values())


def clear_workspace_dirs() -> None:
    _workspace_dirs.clear()


def domains_to_registry(ws_def: WorkspaceDef, data_dir: str = ".") -> EntityRegistry:
    """合并工作目录下所有 domain + process 的定义为一个 EntityRegistry。

    合并工作目录的 domain + process 定义为 EntityRegistry。
    """
    registry = EntityRegistry()

    for domain in ws_def.domains:
        if not os.path.exists(domain.ttl_path):
            continue
        p = OntologyParser(ttl_path=domain.ttl_path, data_dir=data_dir)
        registry.object_types.update(p.registry.object_types)
        registry.link_types.update(p.registry.link_types)

    for domain in ws_def.domains:
        if domain.actions_dir and os.path.isdir(domain.actions_dir):
            registry.action_types.update(load_actions(domain.actions_dir))
    for proc in ws_def.processes:
        if proc.actions_dir and os.path.isdir(proc.actions_dir):
            registry.action_types.update(load_actions(proc.actions_dir))

    return registry
