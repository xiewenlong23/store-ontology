"""认证路由（设计文档 §5 WP2）。

P5：从 main.py 拆出。4 个端点：login / refresh / me / logout。
身份数据存 workspace，agent 层只做编排 + JWT 签发。
"""
import os

from fastapi import APIRouter, Request
from pydantic import BaseModel as BM, Field

from agent.state import auth_ctx

router = APIRouter(prefix="/api/auth", tags=["auth"])

# WP6 强制模式下的豁免路径（auth_middleware 用，此处仅 login 自身需要）。
AUTH_EXEMPT_PATHS = {"/api/auth/login", "/health"}


class LoginRequest(BM):
    username: str = Field(..., description="实名（工号/手机号），跨 workspace 一致")
    password: str


def auth_required() -> bool:
    """是否强制认证。env AUTH_REQUIRED=false 关闭（默认开启）。"""
    val = os.getenv("AUTH_REQUIRED", "true").strip().lower()
    return val not in ("false", "0", "no", "off")


@router.post("/login")
async def auth_login(req: LoginRequest, request: Request):
    """登录：扫描所有 workspace 验证 → 签发 JWT。

    设计文档 §2.2：username 实名一致，password_hash 各 workspace 独立；
    返回 memberships（认成功的 workspace 列表）+ access/refresh token。
    """
    from engine.identity import list_user_workspaces
    from engine.auth import issue_session_tokens
    from engine.auth_audit import log_auth_event

    client_ip = request.client.host if request.client else None
    memberships = list_user_workspaces(req.username, req.password)
    if not memberships:
        log_auth_event("login", username=req.username, outcome="failed",
                       detail="无匹配 workspace 或密码错", client_ip=client_ip)
        return {"success": False, "error": "用户名或密码错误"}

    ws_names = [m["workspace_name"] for m in memberships]
    user_id = memberships[0]["user_id"]
    tokens = issue_session_tokens(user_id=user_id, workspace_names=ws_names)
    log_auth_event("login", username=req.username, user_id=user_id,
                   outcome="success", detail=f"workspaces={ws_names}", client_ip=client_ip)
    return {
        "success": True,
        "token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "session_id": tokens["session_id"],
        "expires_in": tokens["expires_in"],
        "memberships": memberships,
    }


@router.post("/refresh")
async def auth_refresh(request: Request):
    """用 refresh token 换新的 access token。

    P2：当前未实现（refresh token 不含 ws 白名单，无法恢复 membership；
    完整实现留 v2.1）。返回 501 Not Implemented 区分「能力未实现」与
    「逻辑失败」——避免前端按 200 契约误判为本次失败可重试。
    """
    from fastapi.responses import JSONResponse
    from engine.auth_audit import log_auth_event

    client_ip = request.client.host if request.client else None
    log_auth_event("refresh", outcome="failed",
                   detail="501 Not Implemented（refresh 留 v2.1，请重新 login）",
                   client_ip=client_ip)
    return JSONResponse(
        status_code=501,
        content={"detail": "Not Implemented",
                 "reason": "refresh token 流程留 v2.1，请重新 login"})


@router.get("/me")
async def auth_me(request: Request):
    """返回当前认证身份 + memberships + visible_tools（设计文档 §5 WP7 前端用）。

    可信身份来自 auth_ctx contextvar（auth_middleware 注入）。
    visible_tools 由 PermissionEvaluator 求值：列出当前 role 可用的工具。
    """
    from agent.tools.shared import _get_actor, _get_evaluator
    from engine.pack import get_workspace_dir
    from agent.routers._shared import resolve_workspace_name
    import importlib

    auth = auth_ctx.get()
    if not auth.is_authenticated():
        return {"authenticated": False}

    # 求当前 role 的可见工具清单
    visible_tools = []
    try:
        actor = _get_actor()
        evaluator = _get_evaluator()
        role = actor.get("role", "")
        # 内核 8 工具 + 该 workspace 的专属工具
        from agent.tools import (
            query_entity, create_entity, update_entity, traverse_relation,
            execute_action, confirm_action, query_task, update_task)
        kernel_tools = [query_entity, create_entity, update_entity, traverse_relation,
                        execute_action, confirm_action, query_task, update_task]
        for t in kernel_tools:
            name = getattr(t, "name", "")
            if name and evaluator.can_use_tool(role, name).granted:
                visible_tools.append(name)
        # workspace 专属工具
        ws = get_workspace_dir(resolve_workspace_name(request))
        if ws:
            for proc in ws.processes:
                if not proc.tools_module:
                    continue
                try:
                    mod = importlib.import_module(proc.tools_module)
                    for t in getattr(mod, "TOOLS", []):
                        name = getattr(t, "name", "")
                        if name and evaluator.can_use_tool(role, name).granted:
                            visible_tools.append(name)
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001
        pass

    return {
        "authenticated": True,
        "user_id": auth.user_id,
        "session_id": auth.session_id,
        "workspace_names": list(auth.workspace_names),
        "visible_tools": visible_tools,
    }


@router.post("/logout")
async def auth_logout(request: Request):
    """登出（MVP：客户端清 token；服务端 token 撤销列表留 v2.1）。"""
    from engine.auth_audit import log_auth_event
    auth = auth_ctx.get()
    client_ip = request.client.host if request.client else None
    log_auth_event("logout", user_id=auth.user_id or None,
                   outcome="success", client_ip=client_ip)
    return {"success": True, "detail": "客户端请清除本地 token"}
