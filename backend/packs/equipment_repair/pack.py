"""equipment_repair 行业包（P2 结构，从 verticals 迁移）。"""
import os
from engine.pack import IndustryPack, CapabilityDomain, ValueChainProcess, register_pack
from packs.equipment_repair.processes.repair.state_machine import (
    REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)

_BASE = os.path.dirname(os.path.abspath(__file__))

MAINTENANCE = CapabilityDomain(
    name="maintenance", display_name="维修域",
    ttl_path=os.path.join(_BASE, "domains", "maintenance", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "domains", "maintenance", "actions"))

REPAIR = ValueChainProcess(
    name="repair", display_name="设备维修",
    workflow_object_type="RepairTicket",
    workflow_object_id_field="ticket_id",
    state_transitions=REPAIR_TICKET_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    skills_dir=os.path.join(_BASE, "processes", "repair", "skills"),
    tools_module="packs.equipment_repair.processes.repair.tools",
    actions_dir=os.path.join(_BASE, "domains", "maintenance", "actions"),
    system_prompt_intro="你是门店设备维修管理助手。")

EQUIPMENT_REPAIR_PACK = IndustryPack(
    name="equipment_repair", display_name="设备维修行业包",
    domains=[MAINTENANCE],
    processes=[REPAIR],
    data_dir=os.path.join(_BASE, "data"))

register_pack(EQUIPMENT_REPAIR_PACK)
