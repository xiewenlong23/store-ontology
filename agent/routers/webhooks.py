"""后端自动化 webhook 路由（模拟端点）。

P5：从 main.py 拆出。审批回调 + POS 扫码事件。
真实审批/POS 系统集成留 v2，当前为模拟端点。
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/approval")
async def webhook_approval(body: dict):
    """审批回调（模拟端点）→ approve_clearance。

    body: {task_id, approver_id, approved: bool}
    真实审批系统集成留 v2。
    """
    from agent.tools.shared import _get_executor
    from workspace.retail.skills.clearance_workflow.automation import handle_approval
    ex = _get_executor(process_name="clearance")
    try:
        result = handle_approval(ex, task_id=body["task_id"],
                                 approver_id=body["approver_id"],
                                 approved=body.get("approved", True))
        return result
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


@router.post("/pos")
async def webhook_pos(body: dict):
    """POS 扫码事件（模拟端点）→ deduct_stock。

    body: {target_id, task_id, quantity}
    真实 POS 系统集成留 v2。
    """
    from agent.tools.shared import _get_executor
    from workspace.retail.skills.clearance_workflow.automation import handle_pos_scan
    ex = _get_executor(process_name="clearance")
    try:
        result = handle_pos_scan(ex, target_id=body["target_id"],
                                 task_id=body["task_id"], quantity=body["quantity"])
        return result
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
