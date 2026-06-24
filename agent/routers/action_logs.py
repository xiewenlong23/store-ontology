"""admin Action Log 查询 API（spec §6.1）。

仅 admin（system_admin / bootstrap admin）可访问；LLM 无查询 Tool（审计是人的职责，spec D5）。
路径：/api/admin/customers/{cid}/action-logs

require_admin 语义：返回 None 放行 / 返回 JSONResponse(403) 拒绝（与 admin.py 一致）。
"""
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Query, Request

from agent.routers._shared import resolve_workspace_name
from engine.admin_ontology_api import require_admin
from engine.workspace_bootstrap import bootstrap_workspace

router = APIRouter(prefix="/api/admin", tags=["admin-action-logs"])


def _get_log_repo(workspace_name: str):
    """从 workspace 实例取 log_repo（spec §4.1）。路由内单独函数，便于测试 monkeypatch。"""
    inst = bootstrap_workspace(workspace_name)
    if inst.log_repo is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503,
                            detail="该 workspace 未启用 Action Log")
    return inst.log_repo


@router.get("/customers/{cid}/action-logs")
async def list_action_logs(request: Request, cid: str,
                           action_type: Optional[str] = Query(None),
                           actor_id: Optional[str] = Query(None),
                           outcome: Optional[str] = Query(None),
                           failure_type: Optional[str] = Query(None),
                           since: Optional[str] = Query(None),
                           until: Optional[str] = Query(None),
                           limit: int = Query(100, ge=1, le=500),
                           offset: int = Query(0, ge=0)):
    """列出 Action Log（按时间倒序，支持过滤 + 分页）。"""
    ws = resolve_workspace_name(request, cid)
    denied = require_admin(ws)
    if denied is not None:
        return denied
    repo = _get_log_repo(ws)
    # 组装 filter（剔除 None）
    filters = {"limit": limit, "offset": offset}
    for k, v in (("action_type", action_type), ("actor_id", actor_id),
                 ("outcome", outcome), ("failure_type", failure_type),
                 ("since", since), ("until", until)):
        if v is not None:
            filters[k] = v
    items = repo.query(ws, **filters)
    count_filters = {k: v for k, v in filters.items() if k not in ("limit", "offset")}
    total = repo.count(ws, **count_filters)
    return {"items": [asdict(e) for e in items], "total": total}


@router.get("/customers/{cid}/action-logs/{log_id}")
async def get_action_log(request: Request, cid: str, log_id: str):
    """取单条 Action Log 详情（含完整 params / affected_objects）。

    log_id 是 PK，但 query 接口不直接支持 by_id；扫最近 1000 条找（PG 后端远期可加 by_id 优化）。
    """
    ws = resolve_workspace_name(request, cid)
    denied = require_admin(ws)
    if denied is not None:
        return denied
    repo = _get_log_repo(ws)
    rows = repo.query(ws, limit=1000)
    for e in rows:
        if e.log_id == log_id:
            return asdict(e)
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Action Log 不存在")
