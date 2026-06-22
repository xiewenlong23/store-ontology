"""运营看板路由（P4 §4.4）。

P5：从 main.py 拆出。跨域 KPI 指标卡 + 待办列表。
v2（WP6）：用请求级 tenant_ctx（反映 X-Org-Unit-ID header），不再用
inst.tenant_context（硬编码 org_unit_id="*" 的总部视角，越权）。
"""
from fastapi import APIRouter, Request

from engine.workspace_bootstrap import bootstrap_workspace
from engine.tenant import TenantContext
from agent.state import tenant_ctx
from agent.routers._shared import resolve_workspace_name

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/{cid}/metrics")
async def dashboard_metrics(request: Request, cid: str):
    """跨域 KPI 指标卡。"""
    inst = bootstrap_workspace(resolve_workspace_name(request, cid))
    tc = tenant_ctx.get()   # v2（WP6）：请求级，非 inst.tenant_context

    # Task 按 status 分组计数
    tasks = inst.repository.read("Task", tc)
    task_counts = {}
    for t in tasks:
        s = t.get("status", "unknown")
        task_counts[s] = task_counts.get(s, 0) + 1

    # NearExpiryProduct 按 status 分组计数
    neps = inst.repository.read("NearExpiryProduct", tc)
    nep_counts = {}
    for n in neps:
        s = n.get("status", "unknown")
        nep_counts[s] = nep_counts.get(s, 0) + 1

    return {
        "tasks": {"total": len(tasks), "by_status": task_counts},
        "near_expiry": {"total": len(neps), "by_status": nep_counts},
    }


@router.get("/{cid}/todos")
async def dashboard_todos(request: Request, cid: str):
    """待办列表：非终态的 Task（需人介入）。"""
    inst = bootstrap_workspace(resolve_workspace_name(request, cid))
    tc = tenant_ctx.get()   # v2（WP6）：请求级，非 inst.tenant_context
    tasks = inst.repository.read("Task", tc)
    active_statuses = {"created", "pending_approval", "approved", "accepted", "in_progress"}
    todos = [t for t in tasks if t.get("status") in active_statuses]
    return {"todos": todos}
