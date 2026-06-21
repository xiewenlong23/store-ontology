"""测试 clearance 自动化 job（T2/T3）。

job 是后端自动化的核心：无 LLM 在环，直接调 ActionExecutor.execute。
"""
import pytest

from engine.bootstrap import bootstrap
from tests._clearance_helper import build_clearance_executor


def _exec(data_dir):
    """构造指向 data_dir 的 clearance executor。"""
    return build_clearance_executor(data_dir)


def test_expiry_check_job_scraps_expired_task(automation_data_dir):
    """T2: 到期报损 job —— in_progress Task 关联已过期 NEP → create_loss_report。

    断言：Task task_exp → scrapped，NEP nep_exp → scrapped，LossReport 创建，
    loss_quantity = planned - sold = 10 - 3 = 7。
    """
    bootstrap()  # 注册 vertical
    from workspace.retail.skills.clearance_workflow.automation import expiry_check_job
    ex, repo = _exec(automation_data_dir)

    expiry_check_job(ex, tenant_id="jjy")

    task = repo.read_one("Task", "jjy", "task_exp")
    ne = repo.read_one("NearExpiryProduct", "jjy", "nep_exp")
    assert task["status"] == "scrapped"
    assert ne["status"] == "scrapped"
    loss_reports = repo.read("LossReport", "jjy")
    assert len(loss_reports) == 1
    assert loss_reports[0]["loss_quantity"] == 7  # planned 10 - sold 3
    assert loss_reports[0]["task_id"] == "task_exp"


def test_expiry_check_skips_non_expired(automation_data_dir):
    """未过期的 in_progress Task 不应被报损。"""
    bootstrap()
    from workspace.retail.skills.clearance_workflow.automation import expiry_check_job
    ex, repo = _exec(automation_data_dir)
    # task_sold 关联 nep_sold（days_left=5，未过期）
    expiry_check_job(ex, tenant_id="jjy")
    sold_task = repo.read_one("Task", "jjy", "task_sold")
    assert sold_task["status"] == "in_progress"  # 未被报损


def test_inventory_check_completes_soldout_task(automation_data_dir):
    """T3: 售罄完成 job —— in_progress Task 且 sold>=planned → complete_task。"""
    bootstrap()
    from workspace.retail.skills.clearance_workflow.automation import inventory_check_job
    ex, repo = _exec(automation_data_dir)
    inventory_check_job(ex, tenant_id="jjy")
    task = repo.read_one("Task", "jjy", "task_sold")
    ne = repo.read_one("NearExpiryProduct", "jjy", "nep_sold")
    assert task["status"] == "completed"
    assert ne["status"] == "sold_out"


def test_inventory_check_skips_unsold(automation_data_dir):
    """未售罄的 in_progress Task 不应被完成。"""
    bootstrap()
    from workspace.retail.skills.clearance_workflow.automation import inventory_check_job
    ex, repo = _exec(automation_data_dir)
    inventory_check_job(ex, tenant_id="jjy")
    # task_exp: sold=3 < planned=10，未售罄
    task = repo.read_one("Task", "jjy", "task_exp")
    assert task["status"] == "in_progress"


def test_handle_approval_approves(automation_data_dir):
    """T4: 审批 webhook → approve_clearance。需 pending_approval 态 Task。"""
    import json
    from pathlib import Path
    bootstrap()
    # 加一个 pending_approval 的 task
    p = Path(automation_data_dir) / "tasks.json"
    tasks = json.loads(p.read_text(encoding="utf-8"))
    tasks.append({"id": "task_app", "task_type": "clearance", "target_id": "nep_exp",
                  "store_id": "store_001", "assignee_id": "emp_001",
                  "status": "pending_approval", "discount_percent": 50,
                  "planned_quantity": 10, "sold_quantity": 0, "params_json": {},
                  "result_json": {}, "priority": "medium", "notes": "审批测",
                  "created_at": "2026-06-15T09:00:00", "started_at": None,
                  "completed_at": None})
    p.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")

    from workspace.retail.skills.clearance_workflow.automation import handle_approval
    ex, repo = _exec(automation_data_dir)
    result = handle_approval(ex, task_id="task_app", approver_id="rcm_1", approved=True)
    assert result["ok"] is True
    task = repo.read_one("Task", "jjy", "task_app")
    assert task["status"] == "approved"


def test_handle_pos_scan_deducts(automation_data_dir):
    """T4: POS webhook → deduct_stock（stock 减、sold 增）。

    需 in_progress 态 Task（deduct_stock 的 submission_criteria 要求 task.status=in_progress）。
    """
    bootstrap()
    from workspace.retail.skills.clearance_workflow.automation import handle_pos_scan
    ex, repo = _exec(automation_data_dir)
    result = handle_pos_scan(ex, target_id="nep_exp", task_id="task_exp", quantity=2)
    assert result["ok"] is True
    ne = repo.read_one("NearExpiryProduct", "jjy", "nep_exp")
    task = repo.read_one("Task", "jjy", "task_exp")
    assert ne["stock_quantity"] == 5  # 7 - 2
    assert task["sold_quantity"] == 5  # 3 + 2


def test_register_clearance_automation_adds_jobs():
    """register 函数把两个 job 加进 scheduler（不真跑，只验注册）。"""
    bootstrap()
    from engine.scheduler import AutomationScheduler
    from workspace.retail.skills.clearance_workflow.automation import register_clearance_automation
    sched = AutomationScheduler()
    register_clearance_automation(sched, interval_seconds=60)
    # pending 列表应含两个 job（start 前注册）
    assert len(sched._pending) == 2
    job_ids = [jid for jid, _, _ in sched._pending]
    assert "clearance_expiry_check" in job_ids
    assert "clearance_inventory_check" in job_ids


def test_automation_closure_resolves_clearance_process():
    """回归 C2：scheduler 闭包 _get_executor 必须解析到 clearance 价值链流程的 executor，
    而非靠 customer_default→retail→processes[0] 的隐式巧合。

    判据：闭包返回的 executor.config 是 clearance 流程（workflow_object_type=Task）。
    若闭包仍传 vertical=（已忽略）或依赖 processes[0] 顺序，此测试会暴露。
    """
    from engine.workspace_bootstrap import reset_instances
    from workspace.retail.skills.clearance_workflow.automation import register_clearance_automation
    # 提取闭包：register 内部定义的 _get_executor。通过调用 register 并检查其副作用不可行，
    # 故直接验证 automation 模块不再用 vertical= 关键字（源码级契约）。
    import inspect
    from workspace.retail.skills.clearance_workflow import automation
    src = inspect.getsource(automation)
    # 闭包必须用 process_name=（不再用 vertical=）
    assert "_ge(process_name=\"clearance\")" in src or \
           "_get_executor(process_name=\"clearance\")" in src, \
        "scheduler 闭包应显式传 process_name=\"clearance\"，不依赖 processes[0] 巧合"
    assert 'vertical="clearance"' not in src, "scheduler 闭包不应再用 vertical="
