"""equipment_repair vertical 配置注册。

import 时注册到内核 vertical 注册表。main.py bootstrap() 自动发现。
**未改任何内核文件** —— 这就是接入第二 vertical 的全部"接线"。
"""
import os

from engine.vertical import VerticalConfig, register_vertical
from verticals.equipment_repair.state_machine import (
    REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
_VROOT = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE, "..", "data", "equipment_repair")

EQUIPMENT_REPAIR_CONFIG = VerticalConfig(
    name="equipment_repair",
    ttl_path=os.path.join(_VROOT, "ontology", "equipment_repair.ttl"),
    actions_dir=os.path.join(_VROOT, "ontology", "actions"),
    data_dir=_DATA_DIR,
    skills_dir=os.path.join(_VROOT, "skills"),
    system_prompt_intro="你是门店设备维修管理助手。",
    workflow_object_type="RepairTicket",
    workflow_object_id_field="ticket_id",
    state_transitions=REPAIR_TICKET_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    tools_module="verticals.equipment_repair.tools",
)

register_vertical(EQUIPMENT_REPAIR_CONFIG)
