"""admin Action Metrics 查询 API（spec §3.1）。

仅 admin 可访问；从 action_logs 按需聚合（spec M1，无物化表）。
路径：/api/admin/customers/{cid}/action-metrics
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query, Request

from agent.routers._shared import resolve_workspace_name
from engine.admin_ontology_api import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin-action-metrics"])

_DEFAULT_WINDOW_DAYS = 30  # spec M2


def _get_log_repo(workspace_name: str):
    """从 workspace 实例取 log_repo（与 action_logs router 一致）。"""
    from engine.workspace_bootstrap import bootstrap_workspace
    from fastapi import HTTPException
    inst = bootstrap_workspace(workspace_name)
    if inst.log_repo is None:
        raise HTTPException(status_code=503, detail="该 workspace 未启用 Action Log")
    return inst.log_repo


@router.get("/customers/{cid}/action-metrics")
async def get_action_metrics(request: Request, cid: str,
                             since: Optional[str] = Query(None),
                             until: Optional[str] = Query(None),
                             action_type: Optional[str] = Query(None),
                             trigger_source: Optional[str] = Query(None)):
    """聚合 Action Log 产出运维指标（成功率/失败分类/P95 时延）。

    默认窗口 30 天（spec M2）；since/until ISO timestamp 可覆盖。
    """
    ws = resolve_workspace_name(request, cid)
    denied = require_admin(ws)
    if denied is not None:
        return denied

    # 默认窗口：now - 30 天 ~ now
    now = datetime.now()
    if since is None:
        since = (now - timedelta(days=_DEFAULT_WINDOW_DAYS)).isoformat(timespec="seconds")
    if until is None:
        until = now.isoformat(timespec="seconds")

    repo = _get_log_repo(ws)
    return repo.aggregate(ws, since=since, until=until,
                          action_type=action_type, trigger_source=trigger_source)
