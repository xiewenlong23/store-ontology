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


# ============ require_admin（Task 2 填充） ============
