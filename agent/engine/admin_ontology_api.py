"""WP7 admin 本体 CRUD API 辅助 —— JSON↔dataclass 转换 + 鉴权。

设计（spec §3.2/§3.3）：
- ``json_to_object_type`` / ``json_to_link_type`` / ``json_to_action_def``：
  body dict → parser/action_loader 的 dataclass。字段结构与现有 GET 端点
  （``pg_ontology_repo.list_*``）输出对称，故前端 GET 拿到的对象原样 PUT/POST 回去
  能复原（round-trip）。
- ``require_admin``：统一鉴权入口（spec §3.3）。system_admin 角色或 bootstrap 初始
  admin 账号放行；其余返回 403 JSONResponse。供 main.py 的写端点统一调用。

仅纯函数 + 一个鉴权检查；不持状态。
"""
from typing import Optional

from fastapi.responses import JSONResponse

from engine.parser import ObjectType, LinkType, PropertyDef
from engine.action_loader import ActionDefinition


# ============ JSON → dataclass ============

def json_to_object_type(body: dict) -> ObjectType:
    """body dict → ObjectType。

    body 字段（与 pg_ontology_repo.list_object_types 输出对称）：
    id, label, label_zh, comment, storage_file, status, visibility,
    edits_only_via_actions, read_roles, read_except, write_roles, write_except,
    properties: [{name, type, read_roles, read_except, write_roles, write_except}, ...]
    """
    name = body.get("id")
    if not name:
        raise ValueError("Object Type body 缺 id 主键")
    props = [_json_to_property(p) for p in (body.get("properties") or [])]
    return ObjectType(
        id=name,
        label=body.get("label") or "",
        comment=body.get("comment") or "",
        properties=props,
        storage_file=body.get("storage_file") or f"{name.lower()}s.json",
        label_zh=body.get("label_zh") or "",
        status=body.get("status") or "active",
        visibility=body.get("visibility") or "normal",
        edits_only_via_actions=bool(body.get("edits_only_via_actions")),
        read_roles=body.get("read_roles") or "",
        read_except=body.get("read_except") or "",
        write_roles=body.get("write_roles") or "",
        write_except=body.get("write_except") or "",
    )


def _json_to_property(p: dict) -> PropertyDef:
    pname = p.get("name")
    if not pname:
        raise ValueError("property 项缺 name")
    return PropertyDef(
        name=pname,
        type=p.get("type") or "string",
        read_roles=p.get("read_roles") or "",
        read_except=p.get("read_except") or "",
        write_roles=p.get("write_roles") or "",
        write_except=p.get("write_except") or "",
    )


def json_to_link_type(body: dict) -> LinkType:
    """body dict → LinkType（字段与 list_link_types 输出对称）。"""
    name = body.get("id")
    if not name:
        raise ValueError("Link Type body 缺 id 主键")
    return LinkType(
        id=name,
        label=body.get("label") or "",
        domain=body.get("domain") or "",
        range=body.get("range") or "",
        via=body.get("via") or "",
        label_zh=body.get("label_zh") or "",
        comment=body.get("comment") or "",
        use_roles=body.get("use_roles") or "",
        use_except=body.get("use_except") or "",
    )


def json_to_action_def(body: dict) -> ActionDefinition:
    """body dict → ActionDefinition（字段与 list_action_types 输出对称）。

    parameters / side_effects 接受 list；submission_criteria 接受 dict。
    """
    api_name = body.get("api_name")
    if not api_name:
        raise ValueError("Action body 缺 api_name 主键")
    return ActionDefinition(
        api_name=api_name,
        display_name=body.get("display_name") or "",
        description=body.get("description") or "",
        status=body.get("status") or "active",
        target_object_type=body.get("target_object_type") or "",
        edits_object_types=list(body.get("edits_object_types") or []),
        locator_field=body.get("locator_field") or "",
        parameters=list(body.get("parameters") or []),
        submission_criteria=dict(body.get("submission_criteria") or {}),
        side_effects=list(body.get("side_effects") or []),
    )


# ============ require_admin：统一鉴权入口 ============

def _get_actor() -> dict:
    """从 auth_ctx contextvar 派生 actor（转发到 agent.tools.shared._get_actor）。

    单独包一层方便测试 monkeypatch（避免直接 patch shared 模块）。
    """
    from agent.tools.shared import _get_actor as _impl
    return _impl()


def _is_bootstrap_admin_account(ws_name: str, user_id: str) -> bool:
    """检查 user_id 是否为该 workspace 的 bootstrap 初始 admin 账号
    （username=='admin'）。与 main.py 旧 /data 端点判断一致。"""
    if not user_id:
        return False
    from engine.identity import _load_users
    from engine.pack import get_workspace_dir
    ws_def = get_workspace_dir(ws_name)
    if not ws_def or not ws_def.data_dir:
        return False
    for u in _load_users(ws_def.data_dir):
        if u.get("id") == user_id and u.get("username") == "admin":
            return True
    return False


def require_admin(ws_name: str, is_admin_account: Optional[bool] = None) -> Optional[JSONResponse]:
    """鉴权：system_admin 角色或 bootstrap admin 账号放行；其余返回 403。

    返回 None 表示放行；返回 JSONResponse(403) 表示拒绝（调用方直接 return 该对象）。

    is_admin_account：调用方可预算（复用判断结果）传 None 让本函数自查。
    """
    actor = _get_actor()
    role = actor.get("role", "")
    user_id = actor.get("user_id", "")
    if role == "system_admin":
        return None
    if is_admin_account is None:
        is_admin_account = _is_bootstrap_admin_account(ws_name, user_id)
    if is_admin_account:
        return None
    return JSONResponse(
        status_code=403,
        content={"detail": f"无权操作（需 system_admin）", "role": role},
    )

