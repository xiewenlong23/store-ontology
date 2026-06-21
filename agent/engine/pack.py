"""行业包三级结构（P2）：IndustryPack > CapabilityDomain + ValueChainProcess。

CapabilityDomain 提供原子 Object/Link/Action；ValueChainProcess 跨域编排。
pack_to_registry 合并 pack 下所有 domain 的定义为一个 EntityRegistry。
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
    actions_dir: Optional[str] = None  # 流程专属 Action（如 submit/approve/accept）
    system_prompt_intro: str = ""
    description: str = ""


@dataclass
class IndustryPack:
    """行业包：聚合多个 CapabilityDomain + 多个 ValueChainProcess。"""
    name: str
    display_name: str
    domains: List[CapabilityDomain] = field(default_factory=list)
    processes: List[ValueChainProcess] = field(default_factory=list)
    data_dir: str = ""


# ============ pack 注册表 ============

_packs: Dict[str, IndustryPack] = {}


def register_pack(pack: IndustryPack) -> None:
    _packs[pack.name] = pack


def get_pack(name: str) -> Optional[IndustryPack]:
    return _packs.get(name)


def all_packs() -> List[IndustryPack]:
    return list(_packs.values())


def clear_packs() -> None:
    _packs.clear()


def pack_to_registry(pack: IndustryPack, data_dir: str = ".") -> EntityRegistry:
    """合并 pack 下所有 domain + process 的定义为一个 EntityRegistry。

    - 每个 domain 的 TTL 解析出 Object/Link
    - 每个 domain + process 的 actions_dir 加载 Action
    - executor/tools 不关心 Action 来自哪里，按名路由
    """
    registry = EntityRegistry()

    # 解析所有 domain TTL（各自独立 parser，合并 object/link_types）
    for domain in pack.domains:
        if not os.path.exists(domain.ttl_path):
            continue
        p = OntologyParser(ttl_path=domain.ttl_path, data_dir=data_dir)
        registry.object_types.update(p.registry.object_types)
        registry.link_types.update(p.registry.link_types)

    # 加载所有 domain + process 的 Action
    for domain in pack.domains:
        if domain.actions_dir and os.path.isdir(domain.actions_dir):
            registry.action_types.update(load_actions(domain.actions_dir))
    for proc in pack.processes:
        if proc.actions_dir and os.path.isdir(proc.actions_dir):
            registry.action_types.update(load_actions(proc.actions_dir))

    return registry
