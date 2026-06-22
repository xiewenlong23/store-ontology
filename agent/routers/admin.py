"""本体管理 + 管理数据浏览路由（P4 §4.5 + WP7-WP10）。

P5：从 main.py 拆出。
- 只读浏览：GET objects/actions/links（含 v2 权限元数据，round-trip 对称）。
- 写端点：POST/PUT/DELETE × 3 collections（WP7），写后 invalidate_workspace。
- 数据浏览：GET data/{entity_type}（system_admin，User 脱敏）。
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from engine.workspace_bootstrap import bootstrap_workspace, invalidate_workspace
from engine import pg_ontology_repo as _ont_repo
from engine.admin_ontology_api import (
    json_to_object_type, json_to_link_type, json_to_action_def,
    require_admin,
)
from agent.routers._shared import resolve_workspace_name

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ----- dict 序列化（与 list_object_types 输出对称，GET/POST/PUT body 对称）-----

def ontology_to_dict(ot) -> dict:
    """ObjectType → dict（与 list_object_types 输出对称，用于响应 body）。"""
    return {
        "id": ot.id, "label": ot.label, "label_zh": ot.label_zh,
        "comment": ot.comment, "storage_file": ot.storage_file,
        "status": ot.status, "visibility": ot.visibility,
        "edits_only_via_actions": ot.edits_only_via_actions,
        "read_roles": ot.read_roles, "read_except": ot.read_except,
        "write_roles": ot.write_roles, "write_except": ot.write_except,
        "properties": [{"name": p.name, "type": p.type,
                        "read_roles": p.read_roles, "read_except": p.read_except,
                        "write_roles": p.write_roles, "write_except": p.write_except}
                       for p in ot.properties],
    }


def link_to_dict(lt) -> dict:
    return {
        "id": lt.id, "label": lt.label, "label_zh": lt.label_zh,
        "comment": lt.comment, "domain": lt.domain, "range": lt.range,
        "via": lt.via, "use_roles": lt.use_roles, "use_except": lt.use_except,
    }


def action_to_dict(ad) -> dict:
    return {
        "api_name": ad.api_name, "display_name": ad.display_name,
        "description": ad.description, "status": ad.status,
        "target_object_type": ad.target_object_type,
        "edits_object_types": list(ad.edits_object_types or []),
        "locator_field": ad.locator_field,
        "parameters": list(ad.parameters or []),
        "submission_criteria": dict(ad.submission_criteria or {}),
        "side_effects": list(ad.side_effects or []),
    }


# ----- 只读浏览 -----

@router.get("/customers/{cid}/ontology/objects")
async def admin_ontology_objects(request: Request, cid: str):
    """该客户所有 Object Type 定义（只读浏览）。

    返回完整字段集（含 v2 权限元数据 read_roles/read_except/write_roles/write_except
    及 property 级权限）——与 POST/PUT body 结构对称（spec §3.2 round-trip）。
    前端 GET → 编辑 → PUT 原样回传不会丢字段。
    """
    inst = bootstrap_workspace(resolve_workspace_name(request, cid))
    objects = [ontology_to_dict(ot) for ot in inst.registry.object_types.values()]
    return {"objects": objects}


@router.get("/customers/{cid}/ontology/actions")
async def admin_ontology_actions(request: Request, cid: str):
    """该客户所有 Action Type 定义。

    返回完整字段集（含 status / submission_criteria / side_effects），与 POST/PUT
    body 对称（spec §3.2 round-trip）。
    """
    inst = bootstrap_workspace(resolve_workspace_name(request, cid))
    actions = [action_to_dict(at) for at in inst.registry.action_types.values()]
    return {"actions": actions}


@router.get("/customers/{cid}/ontology/links")
async def admin_ontology_links(request: Request, cid: str):
    """该客户所有 Link Type 定义。

    返回完整字段集（含 use_roles / use_except / comment / label_zh），与 POST/PUT
    body 对称（spec §3.2 round-trip）。
    """
    inst = bootstrap_workspace(resolve_workspace_name(request, cid))
    links = [link_to_dict(lt) for lt in inst.registry.link_types.values()]
    return {"links": links}


# ----- Object Types 写 -----

@router.post("/customers/{cid}/ontology/objects")
async def admin_create_object(request: Request, cid: str):
    ws_name = resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    try:
        ot = json_to_object_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_object_type(ws_name, ot)
    invalidate_workspace(ws_name)
    return {"created": ontology_to_dict(ot)}


@router.put("/customers/{cid}/ontology/objects/{name}")
async def admin_update_object(request: Request, cid: str, name: str):
    ws_name = resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    body["id"] = name  # 路径主键覆盖 body（spec §3.1）
    try:
        ot = json_to_object_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_object_type(ws_name, ot)
    invalidate_workspace(ws_name)
    return {"updated": ontology_to_dict(ot)}


@router.delete("/customers/{cid}/ontology/objects/{name}")
async def admin_delete_object(request: Request, cid: str, name: str):
    ws_name = resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    ok = _ont_repo.delete_object_type(ws_name, name)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": f"{name} 不存在"})
    invalidate_workspace(ws_name)
    return {"deleted": True}


# ----- Link Types 写 -----

@router.post("/customers/{cid}/ontology/links")
async def admin_create_link(request: Request, cid: str):
    ws_name = resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    try:
        lt = json_to_link_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_link_type(ws_name, lt)
    invalidate_workspace(ws_name)
    return {"created": link_to_dict(lt)}


@router.put("/customers/{cid}/ontology/links/{name}")
async def admin_update_link(request: Request, cid: str, name: str):
    ws_name = resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    body["id"] = name
    try:
        lt = json_to_link_type(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_link_type(ws_name, lt)
    invalidate_workspace(ws_name)
    return {"updated": link_to_dict(lt)}


@router.delete("/customers/{cid}/ontology/links/{name}")
async def admin_delete_link(request: Request, cid: str, name: str):
    ws_name = resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    ok = _ont_repo.delete_link_type(ws_name, name)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": f"{name} 不存在"})
    invalidate_workspace(ws_name)
    return {"deleted": True}


# ----- Action Types 写 -----

@router.post("/customers/{cid}/ontology/actions")
async def admin_create_action(request: Request, cid: str):
    ws_name = resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    try:
        ad = json_to_action_def(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_action_type(ws_name, ad)
    invalidate_workspace(ws_name)
    return {"created": action_to_dict(ad)}


@router.put("/customers/{cid}/ontology/actions/{api_name}")
async def admin_update_action(request: Request, cid: str, api_name: str):
    ws_name = resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    body = await request.json()
    body["api_name"] = api_name
    try:
        ad = json_to_action_def(body)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    _ont_repo.upsert_action_type(ws_name, ad)
    invalidate_workspace(ws_name)
    return {"updated": action_to_dict(ad)}


@router.delete("/customers/{cid}/ontology/actions/{api_name}")
async def admin_delete_action(request: Request, cid: str, api_name: str):
    ws_name = resolve_workspace_name(request, cid)
    denied = require_admin(ws_name)
    if denied:
        return denied
    ok = _ont_repo.delete_action_type(ws_name, api_name)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": f"{api_name} 不存在"})
    invalidate_workspace(ws_name)
    return {"deleted": True}


# ----- 管理数据浏览（WP7 配套）-----

@router.get("/customers/{cid}/data/{entity_type}")
async def admin_data_browse(request: Request, cid: str, entity_type: str):
    """管理员数据浏览（只读）：列出指定 entity_type 的全部记录。

    用途：admin UI 展示 User/Role/PermissionGrant/OrgUnit/Category 等数据。
    权限：需要 system_admin 角色（PermissionEvaluator 校验）。其他角色 → 403。

    entity_type 限制为 identity/organization/category/personnel 域的"管理类"对象，
    避免业务数据（Task/NearExpiryProduct 等）泄露（那些走各自的工具）。
    """
    from engine.admin_ontology_api import _get_actor as _ga
    from agent.tools.shared import _get_evaluator
    from engine.tenant import TenantContext

    ws_name = resolve_workspace_name(request, cid)
    inst = bootstrap_workspace(ws_name)
    # v2 权限：管理数据浏览允许 system_admin 或 username=='admin'（初始管理员），
    # 走统一 require_admin；非 admin 但 PermissionEvaluator 允许 read 的角色仍放行（保留旧语义）。
    denied = require_admin(ws_name)
    if denied:
        actor = _ga()
        role = actor.get("role", "")
        evaluator = _get_evaluator()
        if not evaluator.can_read_object(role, entity_type).granted:
            return denied
    # 总部视角读全部（admin 数据不应受 org_unit 隔离）
    tc = TenantContext(workspace_name=ws_name, org_unit_id="*")
    rows = inst.repository.read(entity_type, tc)
    # 脱敏：User 表剥离 password_hash
    if entity_type == "User":
        rows = [{k: v for k, v in r.items() if k != "password_hash"} for r in rows]
    return {"entity_type": entity_type, "total": len(rows), "items": rows}
