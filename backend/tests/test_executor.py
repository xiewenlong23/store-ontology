import pytest
from engine.errors import ValidationError
from tests._clearance_helper import build_clearance_executor


def _exec(data_dir):
    return build_clearance_executor(data_dir)


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


def _drive_to_in_progress(ex, clearance_data_dir, qty=50):
    """辅助：把一个出清流程推到 in_progress，返回 task_id。"""
    r = ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": qty,
    }, actor={"role": "store_manager"}, tenant_id="tenant_default")
    task_id = r["created"]["Task"][0]["id"]
    for action, params, role in [
        ("submit_for_approval", {"task_id": task_id}, "store_manager"),
        ("approve_clearance", {"task_id": task_id, "approver_id": "rcm_1"}, "region_cat_mgr"),
        ("accept_task", {"task_id": task_id, "assignee_id": "emp_001"}, "store_manager"),
        ("print_labels", {"task_id": task_id, "label_count": qty}, "store_manager"),
    ]:
        ex.execute(action, params, actor={"role": role}, tenant_id="tenant_default")
    return task_id


def test_complete_task_reaches_terminal(clearance_data_dir):
    """回归：complete_task 终态可达（曾因 _load_target 定位 bug 永远抛错）。"""
    ex, repo = _exec(clearance_data_dir)
    task_id = _drive_to_in_progress(ex, clearance_data_dir, qty=50)
    ex.execute("deduct_stock", {"target_id": "ne_001", "task_id": task_id, "quantity": 50},
               actor={"role": "system_pos"}, tenant_id="tenant_default")
    result = ex.execute("complete_task", {"task_id": task_id, "target_id": "ne_001"},
                        actor={"role": "store_manager"}, tenant_id="tenant_default")
    assert result["ok"] is True
    task = repo.read_one("Task", "tenant_default", task_id)
    ne = repo.read_one("NearExpiryProduct", "tenant_default", "ne_001")
    assert task["status"] == "completed"
    assert ne["status"] == "sold_out"


def test_complete_task_blocked_if_not_in_progress(clearance_data_dir):
    """complete_task 只能从 in_progress 迁移。"""
    ex, _ = _exec(clearance_data_dir)
    task_id = _drive_to_in_progress(ex, clearance_data_dir, qty=50)
    # 直接从 in_progress 又调一次 complete 会因第一次已 completed（终态）被拒
    ex.execute("complete_task", {"task_id": task_id, "target_id": "ne_001"},
               actor={"role": "store_manager"}, tenant_id="tenant_default")
    with pytest.raises(ValidationError):
        ex.execute("complete_task", {"task_id": task_id, "target_id": "ne_001"},
                   actor={"role": "store_manager"}, tenant_id="tenant_default")


def test_create_loss_report_creates_loss_report(clearance_data_dir):
    """回归：create_loss_report 建报损单（曾因 _load_target 定位 bug 永远抛错）。"""
    ex, repo = _exec(clearance_data_dir)
    task_id = _drive_to_in_progress(ex, clearance_data_dir, qty=50)
    # 到期未售罄，报损
    result = ex.execute("create_loss_report", {
        "task_id": task_id, "target_id": "ne_001",
        "loss_quantity": 50, "loss_value": 225.0, "loss_reason": "到期未售罄",
    }, actor={"role": "store_manager"}, tenant_id="tenant_default")
    assert result["ok"] is True
    assert "LossReport" in result["created"]
    lr = result["created"]["LossReport"][0]
    assert lr["task_id"] == task_id
    assert lr["target_id"] == "ne_001"
    task = repo.read_one("Task", "tenant_default", task_id)
    ne = repo.read_one("NearExpiryProduct", "tenant_default", "ne_001")
    assert task["status"] == "scrapped"
    assert ne["status"] == "scrapped"
