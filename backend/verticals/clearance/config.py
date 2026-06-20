"""clearance vertical 的配置注册。

启动时 main.py import 本模块即完成注册。vertical 配置聚合所有路径与工作流元信息，
内核不再硬编码任何 clearance 路径（见 docs/manual/01）。
"""
import os

from ontology.vertical import VerticalConfig, register_vertical
from ontology.state_machine import TASK_TRANSITIONS, TERMINAL_STATES

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
_ROOT = os.path.dirname(_BASE)                                                          # 项目根

CLEARANCE_CONFIG = VerticalConfig(
    name="clearance",
    ttl_path=os.path.join(_BASE, "ontology", "store.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "actions"),
    data_dir=os.path.join(_ROOT, "data"),
    skills_dir=os.path.join(_BASE, "skills"),
    system_prompt_intro="你是门店临期商品管理助手。",
    workflow_object_type="Task",
    workflow_object_id_field="task_id",
    state_transitions=TASK_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    tools_module="verticals.clearance.tools",
)

register_vertical(CLEARANCE_CONFIG)
