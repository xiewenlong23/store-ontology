"""equipment_repair vertical 回归测试（worked example 锁定）。

证明：多 vertical 并存 + 零改内核 + 无折扣概念也能跑。
每个工作流测试用 repair_data_dir fixture（隔离副本），不污染真实 data/equipment_repair/。
"""
import pytest

from ontology.bootstrap import bootstrap
from ontology.vertical import all_verticals
from ontology.parser import OntologyParser
from ontology.action_loader import load_actions
from ontology.repository import JSONFileRepository
from ontology.executor import ActionExecutor
from ontology.errors import ValidationError
from verticals.equipment_repair.state_machine import (
    REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)
from verticals.equipment_repair.config import EQUIPMENT_REPAIR_CONFIG


@pytest.fixture(autouse=True)
def _boot():
    bootstrap()
    yield


def _exec(data_dir):
    """构造指向 data_dir 的 parser+repo+executor（用真实 config 的工作流字段）。"""
    cfg = EQUIPMENT_REPAIR_CONFIG
    p = OntologyParser(ttl_path=cfg.ttl_path, data_dir=data_dir, config=cfg)
    p.registry.action_types = load_actions(cfg.actions_dir)
    repo = JSONFileRepository(data_dir=data_dir, registry=p.registry)
    ex = ActionExecutor(repository=repo, actions=p.registry.action_types,
                        registry=p.registry, config=cfg)
    return ex, repo


def test_equipment_repair_registered():
    names = [c.name for c in all_verticals()]
    assert "clearance" in names and "equipment_repair" in names


def test_repair_ttl_and_actions_parse():
    p = OntologyParser(ttl_path=EQUIPMENT_REPAIR_CONFIG.ttl_path,
                       data_dir=str(__import__("pathlib").Path(EQUIPMENT_REPAIR_CONFIG.data_dir)),
                       config=EQUIPMENT_REPAIR_CONFIG)
    p.registry.action_types = load_actions(EQUIPMENT_REPAIR_CONFIG.actions_dir)
    assert p.PREFIX == "repair:"
    assert {"Equipment", "RepairTicket", "Technician", "Vendor"} == set(p.registry.object_types)
    assert len(p.registry.link_types) == 4
    assert {"create_repair_ticket", "diagnose_ticket", "assign_technician",
            "start_repair", "complete_repair", "cancel_ticket"} == set(p.registry.action_types)


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


def test_clearance_still_works_alongside():
    """clearance 仍注册且可解析（多 vertical 共存）。"""
    from ontology.parser import get_ontology_parser, reset_parser_cache
    reset_parser_cache()
    bootstrap()
    p = get_ontology_parser("clearance")
    assert p.PREFIX == "store:"
    assert "create_clearance_task" in p.registry.action_types


def test_state_machine_table_loaded():
    """equipment_repair 的状态迁移表正确（独立于 clearance）。"""
    assert "repairing" in REPAIR_TICKET_TRANSITIONS
    assert "resolved" in TERMINAL_STATES
    from ontology.state_machine import is_valid_transition
    assert is_valid_transition("reported", "diagnosed", REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)
    assert not is_valid_transition("reported", "repairing", REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)
    assert not is_valid_transition("resolved", "cancelled", REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)
