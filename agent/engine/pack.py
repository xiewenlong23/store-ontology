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
    """能力域：提供原子 Object/Link/Action + 域内规则源。不含工作流/状态机。"""
    name: str
    display_name: str
    ttl_path: str
    actions_dir: str
    rules_dir: Optional[str] = None
    description: str = ""


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


@dataclass
class WorkspaceDef:
    """工作目录定义：一组能力域 + 价值链流程（工作目录定义）。"""
    name: str
    display_name: str
    domains: List[CapabilityDomain] = field(default_factory=list)
    processes: List[ValueChainProcess] = field(default_factory=list)
    data_dir: str = ""


# ============ 工作目录注册表 ============

_workspace_dirs: Dict[str, WorkspaceDef] = {}


def register_workspace_dir(ws_def: WorkspaceDef) -> None:
    _workspace_dirs[ws_def.name] = ws_def


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
