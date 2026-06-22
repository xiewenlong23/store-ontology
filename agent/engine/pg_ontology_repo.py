"""PgOntologyRepository — 本体 schema CRUD on PostgreSQL（WP3，roadmap §1）。

替代 ``domains_to_registry`` 的 TTL/YAML 文件读取——读写 PG 表：
- object_types / object_type_properties / link_types / action_types

设计：
- ``load_registry(ws_name) -> EntityRegistry``：从 PG 装载（与 domains_to_registry 输出格式一致）
- ``upsert_object_type / upsert_link_type / upsert_action_type``：admin CRUD 写路径
- ``delete_*``：级联删（properties 子表通过 FK ON DELETE CASCADE）
- 与 ``parser.py`` 的 ObjectType/LinkType/PropertyDef dataclass 完全兼容（同一内存模型）

PG 未配置时 ``load_registry`` 抛 ``PGNotConfigured``；上层（bootstrap_workspace）应回落 JSON。
"""
import json
from typing import List, Optional

from engine.db import (
    is_pg_enabled, ping, query, query_one, execute, transaction,
    PGNotConfigured, PGNotAvailable,
)
from engine.parser import (
    EntityRegistry, ObjectType, LinkType, PropertyDef,
)
from engine.action_loader import ActionDefinition


# ============ load：PG -> EntityRegistry ============

def load_registry(workspace_name: str) -> EntityRegistry:
    """从 PG 装载 workspace 的本体 schema → EntityRegistry。

    PG 未启用抛 PGNotConfigured；表不存在抛 PGNotAvailable（应先 migrate）。
    """
    if not (is_pg_enabled() and ping()):
        raise PGNotConfigured("PG 未启用或不可用")

    registry = EntityRegistry()

    # 1. Object Types + Properties
    obj_rows = query(
        "SELECT * FROM object_types WHERE workspace_name = %s ORDER BY name",
        (workspace_name,))
    for row in obj_rows:
        props = _load_properties(workspace_name, row["name"])
        registry.object_types[row["name"]] = _row_to_object_type(row, props)

    # 2. Link Types
    link_rows = query(
        "SELECT * FROM link_types WHERE workspace_name = %s ORDER BY name",
        (workspace_name,))
    for row in link_rows:
        registry.link_types[row["name"]] = _row_to_link_type(row)

    # 3. Action Types
    action_rows = query(
        "SELECT * FROM action_types WHERE workspace_name = %s ORDER BY api_name",
        (workspace_name,))
    for row in action_rows:
        ad = _row_to_action_def(row)
        registry.action_types[ad.api_name] = ad

    return registry


def _load_properties(workspace_name: str, object_type_name: str) -> List[PropertyDef]:
    rows = query(
        "SELECT * FROM object_type_properties "
        "WHERE workspace_name = %s AND object_type_name = %s "
        "ORDER BY ordinal",
        (workspace_name, object_type_name))
    return [PropertyDef(
        name=r["name"], type=r["type"],
        read_roles=r.get("read_roles", "") or "",
        read_except=r.get("read_except", "") or "",
        write_roles=r.get("write_roles", "") or "",
        write_except=r.get("write_except", "") or "",
    ) for r in rows]


def _row_to_object_type(row: dict, props: List[PropertyDef]) -> ObjectType:
    label = row.get("label") or ""
    label_zh = row.get("label_zh") or ""
    # 与 parser 一致：label 形如 "中文名 (English)"
    if not label and label_zh:
        label = label_zh
    return ObjectType(
        id=row["name"],
        label=label,
        comment=row.get("comment") or "",
        properties=props,
        storage_file=row.get("storage_file") or f"{row['name'].lower()}s.json",
        label_zh=label_zh,
        status=row.get("status") or "active",
        visibility=row.get("visibility") or "normal",
        edits_only_via_actions=bool(row.get("edits_only_via_actions")),
        read_roles=row.get("read_roles") or "",
        read_except=row.get("read_except") or "",
        write_roles=row.get("write_roles") or "",
        write_except=row.get("write_except") or "",
    )


def _row_to_link_type(row: dict) -> LinkType:
    label = row.get("label") or ""
    label_zh = row.get("label_zh") or ""
    if not label and label_zh:
        label = label_zh
    return LinkType(
        id=row["name"],
        label=label,
        domain=row.get("domain") or "",
        range=row.get("range") or "",
        via=row.get("via") or "",
        label_zh=label_zh,
        comment=row.get("comment") or "",
        use_roles=row.get("use_roles") or "",
        use_except=row.get("use_except") or "",
    )


def _row_to_action_def(row: dict) -> ActionDefinition:
    return ActionDefinition(
        api_name=row["api_name"],
        display_name=row.get("display_name") or "",
        description=row.get("description") or "",
        status=row.get("status") or "active",
        target_object_type=row.get("target_object_type") or "",
        edits_object_types=row.get("edits_object_types") or [],
        locator_field=row.get("locator_field") or "",
        parameters=_ensure_list(row.get("parameters")),
        submission_criteria=_ensure_dict(row.get("submission_criteria")),
        side_effects=_ensure_list(row.get("side_effects")),
    )


def _ensure_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _ensure_dict(v) -> dict:
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


# ============ upsert：admin CRUD 写路径 ============

def upsert_object_type(workspace_name: str, ot: ObjectType) -> None:
    """插入或更新 Object Type（含 properties 子表，全量替换 properties）。"""
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO object_types (
                    workspace_name, name, label, label_zh, comment, storage_file,
                    status, visibility, edits_only_via_actions,
                    read_roles, read_except, write_roles, write_except
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (workspace_name, name) DO UPDATE SET
                    label = EXCLUDED.label,
                    label_zh = EXCLUDED.label_zh,
                    comment = EXCLUDED.comment,
                    storage_file = EXCLUDED.storage_file,
                    status = EXCLUDED.status,
                    visibility = EXCLUDED.visibility,
                    edits_only_via_actions = EXCLUDED.edits_only_via_actions,
                    read_roles = EXCLUDED.read_roles,
                    read_except = EXCLUDED.read_except,
                    write_roles = EXCLUDED.write_roles,
                    write_except = EXCLUDED.write_except
            """, (
                workspace_name, ot.id, ot.label, ot.label_zh, ot.comment,
                ot.storage_file, ot.status, ot.visibility, ot.edits_only_via_actions,
                ot.read_roles, ot.read_except, ot.write_roles, ot.write_except,
            ))
            # properties 全量替换（先删后插；FK ON DELETE CASCADE 也行但显式更清晰）
            cur.execute(
                "DELETE FROM object_type_properties "
                "WHERE workspace_name = %s AND object_type_name = %s",
                (workspace_name, ot.id))
            for ordinal, p in enumerate(ot.properties):
                cur.execute("""
                    INSERT INTO object_type_properties (
                        workspace_name, object_type_name, name, type,
                        read_roles, read_except, write_roles, write_except, ordinal
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    workspace_name, ot.id, p.name, p.type,
                    p.read_roles, p.read_except, p.write_roles, p.write_except,
                    ordinal,
                ))


def upsert_link_type(workspace_name: str, lt: LinkType) -> None:
    execute("""
        INSERT INTO link_types (
            workspace_name, name, label, label_zh, comment,
            domain, range, via, use_roles, use_except
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (workspace_name, name) DO UPDATE SET
            label = EXCLUDED.label,
            label_zh = EXCLUDED.label_zh,
            comment = EXCLUDED.comment,
            domain = EXCLUDED.domain,
            range = EXCLUDED.range,
            via = EXCLUDED.via,
            use_roles = EXCLUDED.use_roles,
            use_except = EXCLUDED.use_except
    """, (
        workspace_name, lt.id, lt.label, lt.label_zh, lt.comment,
        lt.domain, lt.range, lt.via, lt.use_roles, lt.use_except,
    ))


def upsert_action_type(workspace_name: str, at: ActionDefinition) -> None:
    """插入或更新 Action Type（parameters/side_effects/submission_criteria 序列化为 JSONB）。"""
    execute("""
        INSERT INTO action_types (
            workspace_name, api_name, display_name, description, status,
            target_object_type, edits_object_types, locator_field,
            parameters, submission_criteria, side_effects
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (workspace_name, api_name) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description,
            status = EXCLUDED.status,
            target_object_type = EXCLUDED.target_object_type,
            edits_object_types = EXCLUDED.edits_object_types,
            locator_field = EXCLUDED.locator_field,
            parameters = EXCLUDED.parameters,
            submission_criteria = EXCLUDED.submission_criteria,
            side_effects = EXCLUDED.side_effects
    """, (
        workspace_name, at.api_name, at.display_name, at.description, at.status,
        at.target_object_type, list(at.edits_object_types or []), at.locator_field,
        json.dumps(at.parameters or []),
        json.dumps(at.submission_criteria or {}),
        json.dumps(at.side_effects or []),
    ))


# ============ delete ============

def delete_object_type(workspace_name: str, name: str) -> bool:
    """删除 Object Type（properties 子表通过 FK ON DELETE CASCADE 自动删）。"""
    rowcount = execute(
        "DELETE FROM object_types WHERE workspace_name = %s AND name = %s",
        (workspace_name, name))
    return rowcount > 0


def delete_link_type(workspace_name: str, name: str) -> bool:
    rowcount = execute(
        "DELETE FROM link_types WHERE workspace_name = %s AND name = %s",
        (workspace_name, name))
    return rowcount > 0


def delete_action_type(workspace_name: str, api_name: str) -> bool:
    rowcount = execute(
        "DELETE FROM action_types WHERE workspace_name = %s AND api_name = %s",
        (workspace_name, api_name))
    return rowcount > 0


# ============ list：admin UI 用（与现有 /api/admin/.../ontology/* 端点对应） ============

def list_object_types(workspace_name: str) -> List[dict]:
    rows = query(
        "SELECT * FROM object_types WHERE workspace_name = %s ORDER BY name",
        (workspace_name,))
    result = []
    for row in rows:
        props = _load_properties(workspace_name, row["name"])
        result.append({
            "id": row["name"], "label": row.get("label"),
            "label_zh": row.get("label_zh"), "comment": row.get("comment"),
            "storage_file": row.get("storage_file"),
            "status": row.get("status"), "visibility": row.get("visibility"),
            "edits_only_via_actions": bool(row.get("edits_only_via_actions")),
            "read_roles": row.get("read_roles", ""),
            "read_except": row.get("read_except", ""),
            "write_roles": row.get("write_roles", ""),
            "write_except": row.get("write_except", ""),
            "properties": [{"name": p.name, "type": p.type,
                            "read_roles": p.read_roles, "read_except": p.read_except,
                            "write_roles": p.write_roles, "write_except": p.write_except}
                           for p in props],
        })
    return result


def list_link_types(workspace_name: str) -> List[dict]:
    rows = query(
        "SELECT * FROM link_types WHERE workspace_name = %s ORDER BY name",
        (workspace_name,))
    return [{
        "id": r["name"], "label": r.get("label"), "label_zh": r.get("label_zh"),
        "comment": r.get("comment"),
        "domain": r.get("domain"), "range": r.get("range"), "via": r.get("via"),
        "use_roles": r.get("use_roles", ""), "use_except": r.get("use_except", ""),
    } for r in rows]


def list_action_types(workspace_name: str) -> List[dict]:
    rows = query(
        "SELECT * FROM action_types WHERE workspace_name = %s ORDER BY api_name",
        (workspace_name,))
    return [{
        "api_name": r["api_name"], "display_name": r.get("display_name"),
        "description": r.get("description"), "status": r.get("status"),
        "target_object_type": r.get("target_object_type"),
        "edits_object_types": r.get("edits_object_types", []),
        "locator_field": r.get("locator_field"),
        "parameters": _ensure_list(r.get("parameters")),
        "submission_criteria": _ensure_dict(r.get("submission_criteria")),
        "side_effects": _ensure_list(r.get("side_effects")),
    } for r in rows]
