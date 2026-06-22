"""PgDataRepository — 业务数据 CRUD on PostgreSQL（WP4，roadmap §1）。

替代 JSONFileRepository 的 PG 版。读写 entities 表（generic JSONB 列）。

设计：
- 实现与 JSONFileRepository 相同的契约（read/read_one/write/delete）
- TenantContext 过滤走 SQL（OrgTree.visible_units → ANY($array)）
- edits-only-via-actions 检查（与 JSON 一致）
- JSONB data 列存全字段；workspace_name/object_type/id/org_unit_id 既在 JSONB 内
  也在关系列（查询高效）

与 JSONFileRepository 行为差异：
- 无 _org_tree 内嵌（PgDataRepository 不依赖 OrgTree 实例——调用方传 visible_units）
- write 用 INSERT...ON CONFLICT DO UPDATE（原子 upsert）
- delete 用 SQL（不需要 read + rewrite 全文件）
"""
import json
from typing import Optional

from engine.db import is_pg_enabled, ping, query, query_one, execute, transaction
from engine.errors import ActionRequiredError
from engine.repository import Repository, _normalize_tenant
from engine.tenant import TenantContext


class PgDataRepository(Repository):
    """业务数据 PG 实现（entities 表）。

    - workspace_name 硬隔离（WHERE 子句）
    - org_unit_id 范围过滤走 SQL（visible_units 数组 + '*' 通配）
    - edits-only-via-actions 检查（registry 查 ObjectType.edits_only_via_actions）
    - write 强制盖 workspace_name + org_unit_id（与 JSONFileRepository 一致）
    """

    storage_kind = "pg"

    def __init__(self, workspace_name: str, registry):
        self.workspace_name = workspace_name
        self.registry = registry
        # OrgTree 由调用方维护（PG 路径暂不做树形过滤的 SQL 化——
        # read 接受 visible_units 参数，无则视为总部视角）

    def _check_edits_only(self, object_type: str, bypass: bool) -> None:
        obj = self.registry.object_types.get(object_type)
        if obj and getattr(obj, "edits_only_via_actions", False) and not bypass:
            raise ActionRequiredError(
                f"{object_type} 已锁定为 edits-only-via-actions，必须经 Action 修改")

    # ---------- read ----------

    def read(self, object_type: str, tenant, filters: Optional[dict] = None,
             visible_units: Optional[set] = None) -> list[dict]:
        tc = _normalize_tenant(tenant)
        ws = self.workspace_name
        sql_parts = ["SELECT data FROM entities WHERE workspace_name = %s AND object_type = %s"]
        params = [ws, object_type]
        self._append_org_clause(sql_parts, params, tc, visible_units)
        rows = query(" ".join(sql_parts), tuple(params))
        result = [self._decode(r["data"]) for r in rows]
        if filters:
            result = [r for r in result
                      if all(str(r.get(k)) == str(v) for k, v in filters.items())]
        return result

    def read_one(self, object_type: str, tenant, entity_id: str,
                 visible_units: Optional[set] = None) -> Optional[dict]:
        tc = _normalize_tenant(tenant)
        ws = self.workspace_name
        sql_parts = ["SELECT data FROM entities WHERE workspace_name = %s AND object_type = %s AND id = %s"]
        params = [ws, object_type, entity_id]
        self._append_org_clause(sql_parts, params, tc, visible_units)
        row = query_one(" ".join(sql_parts), tuple(params))
        return self._decode(row["data"]) if row else None

    # ---------- write ----------

    def write(self, object_type: str, tenant, record: dict, *,
              create: bool = False, bypass_action_check: bool = False) -> dict:
        tc = _normalize_tenant(tenant)
        ws = self.workspace_name
        self._check_edits_only(object_type, bypass_action_check)
        record = dict(record)
        # 强制盖 workspace_name + org_unit_id（与 JSONFileRepository 一致）
        record["workspace_name"] = ws
        record["org_unit_id"] = tc.org_unit_id
        entity_id = record.get("id")
        if not entity_id:
            raise ValueError("record 必须含 id 字段")
        # upsert：INSERT...ON CONFLICT (workspace_name, object_type, id) DO UPDATE
        execute("""
            INSERT INTO entities (workspace_name, object_type, id, org_unit_id, data)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (workspace_name, object_type, id) DO UPDATE SET
                org_unit_id = EXCLUDED.org_unit_id,
                data = EXCLUDED.data
        """, (ws, object_type, entity_id, tc.org_unit_id, json.dumps(record, default=str)))
        return record

    # ---------- delete ----------

    def delete(self, object_type: str, tenant, entity_id: str,
               visible_units: Optional[set] = None) -> bool:
        tc = _normalize_tenant(tenant)
        ws = self.workspace_name
        sql_parts = ["DELETE FROM entities WHERE workspace_name = %s AND object_type = %s AND id = %s"]
        params = [ws, object_type, entity_id]
        self._append_org_clause(sql_parts, params, tc, visible_units)
        rowcount = execute(" ".join(sql_parts), tuple(params))
        return rowcount > 0

    # ---------- SQL helpers ----------

    @staticmethod
    def _append_org_clause(sql_parts: list, params: list,
                           tc: TenantContext, visible_units: Optional[set]) -> None:
        """向 sql_parts/params 追加 org_unit_id 过滤的 AND 子句。

        - tc.org_unit_id == '*'（总部视角）→ 不追加（不过滤）
        - visible_units 非空 → AND (org_unit_id = ANY(...) OR org_unit_id = '*')
        - visible_units 空 → AND (org_unit_id = $org OR org_unit_id = '*')
        """
        if tc.sees_all_org_units():
            return
        if visible_units:
            sql_parts.append("AND (org_unit_id = ANY(%s) OR org_unit_id = '*')")
            params.append(list(visible_units))
        else:
            sql_parts.append("AND (org_unit_id = %s OR org_unit_id = '*')")
            params.append(tc.org_unit_id)

    @staticmethod
    def _decode(data) -> dict:
        """PG 返回的 JSONB 解码为 dict（psycopg 自动转 dict；兼容 str）。"""
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}
        return dict(data) if hasattr(data, "items") else {}
