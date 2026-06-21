"""equipment_repair 工作目录（示例）。1 能力域 + 1 价值链流程（repair）。"""
import os
from engine.pack import WorkspaceDef, CapabilityDomain, ValueChainProcess, register_workspace_dir
from workspace.equipment_repair.skills.repair_workflow.state_machine import (
    REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)

_BASE = os.path.dirname(os.path.abspath(__file__))

MAINTENANCE = CapabilityDomain(
    name="maintenance", display_name="维修域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "maintenance", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "maintenance", "actions"))

REPAIR = ValueChainProcess(
    name="repair", display_name="设备维修",
    workflow_object_type="RepairTicket",
    workflow_object_id_field="ticket_id",
    state_transitions=REPAIR_TICKET_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    skills_dir=os.path.join(_BASE, "skills"),
    tools_module="workspace.equipment_repair.skills.repair_workflow.tools",
    actions_dir=os.path.join(_BASE, "ontology", "domains", "maintenance", "actions"),
    system_prompt_intro="你是门店设备维修管理助手。")

EQUIPMENT_REPAIR_WS = WorkspaceDef(
    name="equipment_repair", display_name="设备维修（示例）",
    domains=[MAINTENANCE],
    processes=[REPAIR],
    data_dir=os.path.join(_BASE, "data"))

register_workspace_dir(EQUIPMENT_REPAIR_WS)
