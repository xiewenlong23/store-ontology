"""Vertical 配置 —— 每个业务 vertical 一个实例，聚合其所有路径与元信息。

设计目的（见 docs/manual/01-内核多vertical改造.md）：
让 kernel 不再硬编码任何 vertical 的路径/字符串。kernel 只认 VerticalConfig；
vertical 自带 config，启动时注册到 registry，main.py/tools 自动聚合。

一个 vertical = 一组自洽的 Object/Link/Action + 工作流(可选) + Skill + 种子。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class VerticalConfig:
    """单个 vertical 的配置。

    必填：name / ttl_path / actions_dir / data_dir。
    工作流相关（可选）：有状态机的 vertical 填 workflow_object_type + state_transitions + terminal_states；
                      无工作流（纯 CRUD）的可不填。
    """
    name: str                                   # vertical 标识，如 "clearance" / "equipment_repair"
    ttl_path: str                               # 本体 TTL 文件绝对/相对路径
    actions_dir: str                            # Action YAML 目录
    data_dir: str                               # 种子数据目录
    skills_dir: Optional[str] = None            # Skill 目录（给 main.py 扫描）
    system_prompt_intro: str = ""               # 系统提示开场白（领域无关表述）
    # 工作流（可选）
    workflow_object_type: Optional[str] = None  # 工作流主对象类型，如 "Task" / "RepairTicket"
    workflow_object_id_field: str = "task_id"   # 工作流对象在 Action 参数里的定位键，如 "task_id" / "ticket_id"
    state_transitions: Dict[str, List[str]] = field(default_factory=dict)  # 状态迁移表
    terminal_states: List[str] = field(default_factory=list)               # 终态集合
    # vertical 专属工具（可选）：模块路径，main.py 聚合时 import 取其 TOOLS 列表
    tools_module: Optional[str] = None          # 如 "verticals.clearance.tools"

    def has_workflow(self) -> bool:
        return self.workflow_object_type is not None and bool(self.state_transitions)


# ============ vertical 注册表（全局单例）============

_registry: Dict[str, VerticalConfig] = {}


def register_vertical(config: VerticalConfig) -> None:
    """注册一个 vertical。同名覆盖（便于热重载）。"""
    _registry[config.name] = config


def get_vertical(name: str) -> Optional[VerticalConfig]:
    return _registry.get(name)


def all_verticals() -> List[VerticalConfig]:
    return list(_registry.values())


def clear_registry() -> None:
    """测试用：清空注册表。"""
    _registry.clear()
