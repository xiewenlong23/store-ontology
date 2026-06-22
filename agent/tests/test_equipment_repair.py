"""customerA pack 回归测试。

证明：多 pack 并存 + 无折扣概念也能跑。
"""
import os
import pytest

from engine.bootstrap import bootstrap
from engine.pack import all_workspace_dirs, domains_to_registry, ValueChainProcess
from engine.parser import OntologyParser
from engine.action_loader import load_actions
from engine.repository import JSONFileRepository
from engine.executor import ActionExecutor
from engine.errors import ValidationError
from workspace.customerA.skills.repair_workflow.state_machine import (
    REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)

_REPAIR_PROCESS = ValueChainProcess(
    name="repair",
    display_name="设备维修",
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
    from engine.pack import get_workspace_dir
    ws = get_workspace_dir("customerA")
    registry = domains_to_registry(ws, data_dir=data_dir)
    repo = JSONFileRepository(data_dir=data_dir, registry=registry)
    ex = ActionExecutor(repository=repo, actions=registry.action_types,
                        registry=registry, config=_REPAIR_PROCESS)
    return ex, repo


def test_customerA_registered():
    names = [p.name for p in all_workspace_dirs()]
    assert "customerA" in names


def test_repair_ttl_and_actions_parse():
    from engine.pack import get_workspace_dir
    ws = get_workspace_dir("customerA")
    registry = domains_to_registry(ws, data_dir=os.path.join(_BASE, "..", "workspace", "customerA", "data"))
    # 业务实体（maintenance domain）应完整存在；identity domain（User/Role/...）可能并存
    business_objects = {"Equipment", "RepairTicket", "Technician", "Vendor"}
    assert business_objects.issubset(set(registry.object_types))
    # maintenance domain 的 4 个 Link 完整存在（identity domain 的 link 不计入此数）
    maintenance_links = {"uses_equipment", "assigned_to", "supplied_by", "has_ticket"}
    assert maintenance_links.issubset(set(registry.link_types))
    assert {"create_repair_ticket", "diagnose_ticket", "assign_technician",
            "start_repair", "complete_repair", "cancel_ticket"} == set(registry.action_types)


def test_full_repair_workflow(repair_data_dir):
    ex, repo = _exec(repair_data_dir)
    r = ex.execute("create_repair_ticket",
                   {"equipment_id": "equip_001", "store_id": "store_001",
                    "reporter_id": "emp_001", "fault_description": "不制冷"},
                   actor={"role": "clerk"}, tenant_id="customerA")
    tid = r["created"]["RepairTicket"][0]["id"]
    assert repo.read_one("Equipment", "customerA", "equip_001")["status"] == "in_repair"
    for action, params, role in [
        ("diagnose_ticket", {"ticket_id": tid, "diagnosis": "压缩机故障"}, "technician"),
        ("assign_technician", {"ticket_id": tid, "technician_id": "tech_001"}, "store_manager"),
        ("start_repair", {"ticket_id": tid}, "technician"),
        ("complete_repair", {"ticket_id": tid, "equipment_id": "equip_001",
                             "parts_cost": 200, "labor_cost": 100}, "technician"),
    ]:
        ex.execute(action, params, actor={"role": role}, tenant_id="customerA")
    t = repo.read_one("RepairTicket", "customerA", tid)
    e = repo.read_one("Equipment", "customerA", "equip_001")
    assert t["status"] == "resolved"
    assert t["parts_cost"] == 200 and t["labor_cost"] == 100
    assert e["status"] == "normal"


def test_illegal_transition_rejected(repair_data_dir):
    ex, _ = _exec(repair_data_dir)
    r = ex.execute("create_repair_ticket",
                   {"equipment_id": "equip_003", "store_id": "store_002",
                    "reporter_id": "emp_003", "fault_description": "x"},
                   actor={"role": "clerk"}, tenant_id="customerA")
    tid = r["created"]["RepairTicket"][0]["id"]
    # reported -> repairing 跳步，应被拒
    with pytest.raises(ValidationError):
        ex.execute("start_repair", {"ticket_id": tid},
                   actor={"role": "technician"}, tenant_id="customerA")


def test_cancel_from_any_nonterminal(repair_data_dir):
    ex, repo = _exec(repair_data_dir)
    r = ex.execute("create_repair_ticket",
                   {"equipment_id": "equip_003", "store_id": "store_002",
                    "reporter_id": "emp_003", "fault_description": "x"},
                   actor={"role": "clerk"}, tenant_id="customerA")
    tid = r["created"]["RepairTicket"][0]["id"]
    ex.execute("cancel_ticket", {"ticket_id": tid, "equipment_id": "equip_003"},
               actor={"role": "store_manager"}, tenant_id="customerA")
    t = repo.read_one("RepairTicket", "customerA", tid)
    e = repo.read_one("Equipment", "customerA", "equip_003")
    assert t["status"] == "cancelled"
    assert e["status"] == "normal"


def test_retail_pack_still_works_alongside():
    """retail pack 仍注册且可解析（pack + vertical 共存）。"""
    from engine.pack import get_workspace_dir, domains_to_registry
    bootstrap()
    ws = get_workspace_dir("retail")
    assert ws is not None
    reg = domains_to_registry(ws, data_dir="../data")
    assert "create_clearance_task" in reg.action_types


def test_query_repair_tickets_tool_invokes_without_error(repair_data_dir, monkeypatch):
    """回归 C1：query_repair_tickets 工具必须能被实际调用（曾因 _get_repo(字符串,...) 崩溃）。

    工具经 shared._get_repo(tc) 装配；此处 monkeypatch 指向 repair_data_dir 的 repo，
    验证工具签名（workspace_name/org_unit_id + TenantContext）与调用链正确。
    """
    from workspace.customerA.skills.repair_workflow.tools import query_repair_tickets
    _, repo = _exec(repair_data_dir)
    import agent.tools.shared as T
    monkeypatch.setattr(T, "_get_repo", lambda tc=None, vertical=None: repo)
    # invoke 走 @tool 的参数解包；workspace_name/org_unit_id 是工具参数
    out = query_repair_tickets.invoke({"workspace_name": "jjy"})
    assert "repair_ticket_list" in out  # 返回格式正确，未抛 AttributeError


def test_state_machine_table_loaded():
    """customerA 的状态迁移表正确（独立于 clearance）。"""
    assert "repairing" in REPAIR_TICKET_TRANSITIONS
    assert "resolved" in TERMINAL_STATES
    from engine.state_machine import is_valid_transition
    assert is_valid_transition("reported", "diagnosed", REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)
    assert not is_valid_transition("reported", "repairing", REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)
    assert not is_valid_transition("resolved", "cancelled", REPAIR_TICKET_TRANSITIONS, TERMINAL_STATES)
