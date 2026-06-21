"""clearance 价值链流程的后端自动化（架构文档 §2.4 步骤 9/12/13/14）。

无 LLM 在环，直接调 ActionExecutor.execute（headless 路径）。
- expiry_check_job: 到期未售罄 → create_loss_report（计算式，无 LLM）
- inventory_check_job: 售罄 → complete_task
- handle_approval / handle_pos_scan: webhook 回调（见 main.py 路由）
"""
from typing import Optional

from engine.errors import OntologyError


def _iter_in_progress_tasks(repo, tenant_id):
    """枚举所有 in_progress 的 Task。"""
    return [t for t in repo.read("Task", tenant_id) if t.get("status") == "in_progress"]


def expiry_check_job(executor, tenant_id: str = "tenant_default") -> int:
    """到期报损：查 in_progress Task，若关联 NEP 已过期(days_left<0)，建报损单。

    loss_quantity = planned_quantity - sold_quantity（计算式，无 LLM 推理）。
    返回处理的任务数。
    """
    repo = executor.repo
    products = {p["id"]: p for p in repo.read("Product", tenant_id)}
    count = 0
    for task in _iter_in_progress_tasks(repo, tenant_id):
        ne = repo.read_one("NearExpiryProduct", tenant_id, task.get("target_id"))
        if not ne or ne.get("days_left", 0) >= 0:
            continue  # 未过期，跳过
        loss_qty = task.get("planned_quantity", 0) - task.get("sold_quantity", 0)
        if loss_qty <= 0:
            continue  # 已售罄，走 complete 而非报损
        prod = products.get(ne.get("product_id"), {})
        loss_value = round(loss_qty * prod.get("cost_price", 0), 2)
        try:
            executor.execute("create_loss_report", {
                "task_id": task["id"],
                "target_id": task["target_id"],
                "loss_quantity": loss_qty,
                "loss_value": loss_value,
                "loss_reason": f"到期未售罄自动报损（剩余{ne.get('days_left')}天）",
            }, actor={"role": "system_scheduler"}, tenant_id=tenant_id)
            count += 1
        except OntologyError:
            continue  # 单个失败不阻塞其它
    return count


def inventory_check_job(executor, tenant_id: str = "tenant_default") -> int:
    """售罄完成：查 in_progress Task，若 sold>=planned，complete_task。返回处理数。"""
    repo = executor.repo
    count = 0
    for task in _iter_in_progress_tasks(repo, tenant_id):
        if task.get("sold_quantity", 0) < task.get("planned_quantity", 0):
            continue  # 未售罄
        try:
            executor.execute("complete_task", {
                "task_id": task["id"],
                "target_id": task["target_id"],
            }, actor={"role": "system_inventory"}, tenant_id=tenant_id)
            count += 1
        except OntologyError:
            continue
    return count


def handle_approval(executor, task_id: str, approver_id: str, approved: bool,
                    tenant_id: str = "tenant_default") -> dict:
    """审批回调 webhook → approve_clearance（approved=True）。

    approved=False 的拒绝路径留后续（reject_clearance Action 未建模）。
    """
    if not approved:
        return {"ok": False, "error": "拒绝路径未实现（reject_clearance 待建模）"}
    return executor.execute("approve_clearance", {
        "task_id": task_id, "approver_id": approver_id,
    }, actor={"role": "region_cat_mgr"}, tenant_id=tenant_id)


def handle_pos_scan(executor, target_id: str, task_id: str, quantity: int,
                    tenant_id: str = "tenant_default") -> dict:
    """POS 扫码 webhook → deduct_stock。"""
    return executor.execute("deduct_stock", {
        "target_id": target_id, "task_id": task_id, "quantity": quantity,
    }, actor={"role": "system_pos"}, tenant_id=tenant_id)


def register_clearance_automation(scheduler, interval_seconds: int = 1800) -> None:
    """把 clearance 的两个定时 job 加进调度器。"""
    # job 闭包需要 executor；延迟获取（main.py 启动后 workspace 已装配）。
    # 显式传 process_name="clearance" 精确选 retail 包下的 clearance 价值链流程，
    # 不依赖 customer_default→retail→processes[0] 的隐式巧合（spec §5.3）。
    def _get_executor():
        from agent.tools import _get_executor as _ge
        return _ge(process_name="clearance")

    def expiry_tick():
        expiry_check_job(_get_executor())

    def inventory_tick():
        inventory_check_job(_get_executor())

    scheduler.add_job("clearance_expiry_check", expiry_tick, interval_seconds)
    scheduler.add_job("clearance_inventory_check", inventory_tick, interval_seconds)
