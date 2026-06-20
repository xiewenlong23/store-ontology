"""equipment_repair pack 回归测试。

证明：多 pack 并存 + 无折扣概念也能跑。
"""
import os
import pytest

from engine.bootstrap import bootstrap
from engine.pack import all_packs, pack_to_registry
from engine.parser import OntologyParser
from engine.action_loader import load_actions
from engine.repository import JSONFileRepository
from engine.executor import ActionExecutor
from engine.errors import ValidationError
from engine.vertical import VerticalConfig
from packs.equipment_repair.processes.repair.state_machine import (
    REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)

_REPAIR_CFG = VerticalConfig(
    name="equipment_repair",
    ttl_path="", actions_dir="", data_dir="",
    workflow_object_type="RepairTicket",
    workflow_object_id_field="ticket_id",
    state_transitions=REPAIR_TICKET_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
)

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _boot():
    bootstrap()
    yield


def _exec(data_dir):
    """构造指向 data_dir 的 executor（从 pack 合并 registry）。"""
    from engine.pack import get_pack
    pack = get_pack("equipment_repair")
    registry = pack_to_registry(pack, data_dir=data_dir)
    repo = JSONFileRepository(data_dir=data_dir, registry=registry)
    ex = ActionExecutor(repository=repo, actions=registry.action_types,
                        registry=registry, config=_REPAIR_CFG)
    return ex, repo


def test_equipment_repair_registered():
    names = [p.name for p in all_packs()]
    assert "equipment_repair" in names


def test_repair_ttl_and_actions_parse():
    from engine.pack import get_pack
    pack = get_pack("equipment_repair")
    registry = pack_to_registry(pack, data_dir=os.path.join(_BASE, "packs", "equipment_repair", "data"))
    assert {"Equipment", "RepairTicket", "Technician", "Vendor"} == set(registry.object_types)
    assert len(registry.link_types) == 4
    assert {"create_repair_ticket", "diagnose_ticket", "assign_technician",
            "start_repair", "complete_repair", "cancel_ticket"} == set(registry.action_types)


def test_full_repair_workflow(repair_data_dir):
    ex, repo = _exec(repair_data_dir)
    r = ex.execute("create_repair_ticket",
                   {"equipment_id": "equip_001", "store_id": "store_001",
                    "reporter_id": "emp_001", "fault_description": "不制冷"},
                   actor={"role": "clerk"}, tenant_id="tenant_default")
    tid = r["created"]["RepairTicket"][0]["id"]
    assert repo.read_one("Equipment", "tenant_default", "equip_001")["status"] == "in_repair"
    for action, params, role in [
        ("diagnose_ticket", {"ticket_id": tid, "diagnosis": "压缩机故障"}, "technician"),
        ("assign_technician", {"ticket_id": tid, "technician_id": "tech_001"}, "store_manager"),
        ("start_repair", {"ticket_id": tid}, "technician"),
        ("complete_repair", {"ticket_id": tid, "equipment_id": "equip_001",
                             "parts_cost": 200, "labor_cost": 100}, "technician"),
    ]:
        ex.execute(action, params, actor={"role": role}, tenant_id="tenant_default")
    t = repo.read_one("RepairTicket", "tenant_default", tid)
    e = repo.read_one("Equipment", "tenant_default", "equip_001")
    assert t["status"] == "resolved"
    assert t["parts_cost"] == 200 and t["labor_cost"] == 100
    assert e["status"] == "normal"


def test_illegal_transition_rejected(repair_data_dir):
    ex, _ = _exec(repair_data_dir)
    r = ex.execute("create_repair_ticket",
                   {"equipment_id": "equip_003", "store_id": "store_002",
                    "reporter_id": "emp_003", "fault_description": "x"},
                   actor={"role": "clerk"}, tenant_id="tenant_default")
    tid = r["created"]["RepairTicket"][0]["id"]
    # reported -> repairing 跳步，应被拒
    with pytest.raises(ValidationError):
        ex.execute("start_repair", {"ticket_id": tid},
                   actor={"role": "technician"}, tenant_id="tenant_default")


def test_cancel_from_any_nonterminal(repair_data_dir):
    ex, repo = _exec(repair_data_dir)
    r = ex.execute("create_repair_ticket",
                   {"equipment_id": "equip_003", "store_id": "store_002",
                    "reporter_id": "emp_003", "fault_description": "x"},
                   actor={"role": "clerk"}, tenant_id="tenant_default")
    tid = r["created"]["RepairTicket"][0]["id"]
    ex.execute("cancel_ticket", {"ticket_id": tid, "equipment_id": "equip_003"},
               actor={"role": "store_manager"}, tenant_id="tenant_default")
    t = repo.read_one("RepairTicket", "tenant_default", tid)
    e = repo.read_one("Equipment", "tenant_default", "equip_003")
    assert t["status"] == "cancelled"
    assert e["status"] == "normal"


def test_retail_pack_still_works_alongside():
    """retail pack 仍注册且可解析（pack + vertical 共存）。"""
    from engine.pack import get_pack, pack_to_registry
    bootstrap()
    pack = get_pack("retail")
    assert pack is not None
    reg = pack_to_registry(pack, data_dir="../data")
    assert "create_clearance_task" in reg.action_types


def test_state_machine_table_loaded():
    """equipment_repair 的状态迁移表正确（独立于 clearance）。"""
    assert "repairing" in REPAIR_TICKET_TRANSITIONS
    assert "resolved" in TERMINAL_STATES
    from engine.state_machine import is_valid_transition
    assert is_valid_transition("reported", "diagnosed", REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)
    assert not is_valid_transition("reported", "repairing", REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)
    assert not is_valid_transition("resolved", "cancelled", REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)
