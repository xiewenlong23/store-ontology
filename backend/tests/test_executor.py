import pytest
from ontology.repository import JSONFileRepository
from ontology.parser import OntologyParser
from ontology.action_loader import load_actions
from ontology.executor import ActionExecutor
from ontology.errors import ValidationError


def _exec(data_dir):
    parser = OntologyParser(ttl_path="ontology/store.ttl", data_dir=data_dir)
    parser.registry.action_types = load_actions("ontology/actions")
    repo = JSONFileRepository(data_dir=data_dir, registry=parser.registry)
    return ActionExecutor(repository=repo, actions=parser.registry.action_types,
                          registry=parser.registry), repo


def test_create_clearance_task_creates_task_and_sets_status(clearance_data_dir):
    ex, repo = _exec(clearance_data_dir)
    result = ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager", "id": "emp_001"},
       tenant_id="tenant_default")
    assert result["ok"] is True
    task = result["created"]["Task"][0]
    assert task["status"] == "created"
    assert task["discount_percent"] == 30
    ne = repo.read_one("NearExpiryProduct", "tenant_default", "ne_001")
    assert ne["status"] == "clearance"


def test_invalid_discount_rejected(clearance_data_dir):
    ex, _ = _exec(clearance_data_dir)
    with pytest.raises(ValidationError):
        ex.execute("create_clearance_task", {
            "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
            "discount_percent": 150, "planned_quantity": 50,
        }, actor={"role": "store_manager"}, tenant_id="tenant_default")


def test_expired_product_blocked(clearance_data_dir):
    import json
    from pathlib import Path
    p = Path(clearance_data_dir) / "near_expiry_products.json"
    rows = json.loads(p.read_text(encoding="utf-8"))
    rows[0]["status"] = "expired"
    p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    ex, _ = _exec(clearance_data_dir)
    with pytest.raises(ValidationError):
        ex.execute("create_clearance_task", {
            "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
            "discount_percent": 30, "planned_quantity": 50,
        }, actor={"role": "store_manager"}, tenant_id="tenant_default")


def test_state_transition_enforced(clearance_data_dir):
    ex, repo = _exec(clearance_data_dir)
    r = ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager"}, tenant_id="tenant_default")
    task_id = r["created"]["Task"][0]["id"]
    # 跳过 submit 直接 accept：应被拒（created !-> accepted）
    with pytest.raises(ValidationError):
        ex.execute("accept_task", {"task_id": task_id, "assignee_id": "emp_001"},
                   actor={"role": "store_manager"}, tenant_id="tenant_default")


def test_deduct_stock_decrements_and_increments(clearance_data_dir):
    ex, repo = _exec(clearance_data_dir)
    r = ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager"}, tenant_id="tenant_default")
    task_id = r["created"]["Task"][0]["id"]
    # 推到 in_progress
    for action, params, role in [
        ("submit_for_approval", {"task_id": task_id}, "store_manager"),
        ("approve_clearance", {"task_id": task_id, "approver_id": "rcm_1"}, "region_cat_mgr"),
        ("accept_task", {"task_id": task_id, "assignee_id": "emp_001"}, "store_manager"),
        ("print_labels", {"task_id": task_id, "label_count": 50}, "store_manager"),
    ]:
        ex.execute(action, params, actor={"role": role}, tenant_id="tenant_default")
    ex.execute("deduct_stock", {"target_id": "ne_001", "task_id": task_id, "quantity": 10},
               actor={"role": "system_pos"}, tenant_id="tenant_default")
    ne = repo.read_one("NearExpiryProduct", "tenant_default", "ne_001")
    task = repo.read_one("Task", "tenant_default", task_id)
    assert ne["stock_quantity"] == 40
    assert task["sold_quantity"] == 10
