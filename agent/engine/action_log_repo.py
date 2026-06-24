"""ActionLogRepository —— Action Log 存储抽象 + 双后端实现（spec §4）。

PG：专用 action_logs 表（带索引，永久保留）
JSON：workspace/<ws>/data/action_logs.json（append-only array，50000 条滚动）

工厂 build_action_log_repo：PG 可用则 PgActionLogRepository，否则 JSON。
与 build_data_repository 同模式。
"""
import json
import os
import threading
from typing import List, Optional

from engine.action_log import ActionLogEntry, mask_sensitive_params
from engine.db import is_pg_enabled, ping

# JSON 后端滚动上限（spec §10.1 决议：50000 条，兼顾永久保留意图与文件可操作性）
_JSON_CAP = 50000


class ActionLogRepository:
    storage_kind: str  # "pg" / "json"

    def write(self, entry: ActionLogEntry) -> None:
        raise NotImplementedError

    def query(self, ws_name: str, *, action_type: Optional[str] = None,
              actor_id: Optional[str] = None, outcome: Optional[str] = None,
              failure_type: Optional[str] = None,
              since: Optional[str] = None, until: Optional[str] = None,
              limit: int = 100, offset: int = 0) -> List[ActionLogEntry]:
        raise NotImplementedError

    def count(self, ws_name: str, **filters) -> int:
        raise NotImplementedError


class JSONFileActionLogRepository(ActionLogRepository):
    """workspace/<ws>/data/action_logs.json append-only（spec §4.1）。

    与 auth_audit.json 同构（atomic temp replace + threading.Lock），但 50000 条滚动。
    params 写入时掩码敏感字段（spec §7.1）。
    """
    storage_kind = "json"

    def __init__(self, data_dir: str, workspace_name: str):
        self._path = os.path.join(data_dir, "action_logs.json")
        self._lock = threading.Lock()
        self._cap = _JSON_CAP  # 测试可覆盖
        os.makedirs(data_dir, exist_ok=True)

    def write(self, entry: ActionLogEntry) -> None:
        entry.params = mask_sensitive_params(entry.params)
        try:
            with self._lock:
                rows = self._load()
                rows.append(_entry_to_dict(entry))
                if len(rows) > self._cap:
                    rows = rows[-self._cap:]
                self._save(rows)
        except Exception as e:  # noqa: BLE001 - 审计失败不阻断请求（spec §7.3）
            print(f"[action_log] JSON write 失败（不影响请求）: {e}")

    def query(self, ws_name: str, **filters) -> List[ActionLogEntry]:
        rows = [r for r in self._load()
                if r.get("workspace_name") == ws_name]
        rows = _apply_filters(rows, filters)
        return [_dict_to_entry(r) for r in rows]

    def count(self, ws_name: str, **filters) -> int:
        count_filters = {k: v for k, v in filters.items()
                         if k not in ("limit", "offset")}
        # count 不受分页影响
        rows = [r for r in self._load()
                if r.get("workspace_name") == ws_name]
        rows = _apply_filters(rows, {**count_filters, "limit": 10**9, "offset": 0})
        return len(rows)

    def _load(self) -> list:
        if not os.path.exists(self._path):
            return []
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, rows: list) -> None:
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)


class PgActionLogRepository(ActionLogRepository):
    """PG action_logs 表实现（spec §4.1）。

    params 写入时掩码敏感字段（spec §7.1）；jsonb 列用 psycopg.types.json.Jsonb。
    """
    storage_kind = "pg"

    def __init__(self, workspace_name: str):
        self.workspace_name = workspace_name

    def write(self, entry: ActionLogEntry) -> None:
        from psycopg.types.json import Jsonb
        from engine.db import execute
        masked = mask_sensitive_params(entry.params)
        try:
            execute("""
                INSERT INTO action_logs
                    (log_id, workspace_name, timestamp, action_type, outcome,
                     failure_type, error_message, actor_id, actor_role, actor_type,
                     trigger_source, edits_object_types, affected_objects,
                     params, duration_ms, llm_model, skill_id, session_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                entry.log_id, entry.workspace_name, entry.timestamp,
                entry.action_type, entry.outcome, entry.failure_type,
                entry.error_message, entry.actor_id, entry.actor_role,
                entry.actor_type, entry.trigger_source,
                entry.edits_object_types or [],
                Jsonb(entry.affected_objects or {}),
                Jsonb(masked) if masked is not None else None,
                entry.duration_ms, entry.llm_model, entry.skill_id, entry.session_id,
            ))
        except Exception as e:  # noqa: BLE001 - 审计失败不阻断请求（spec §7.3）
            print(f"[action_log] PG write 失败（不影响请求）: {e}")

    def query(self, ws_name: str, **filters) -> List[ActionLogEntry]:
        from engine.db import query as db_query
        clauses = ["workspace_name = %s"]
        params: list = [ws_name]
        for key, col in (("action_type", "action_type"), ("actor_id", "actor_id"),
                         ("outcome", "outcome"), ("failure_type", "failure_type")):
            if filters.get(key):
                clauses.append(f"{col} = %s")
                params.append(filters[key])
        if filters.get("since"):
            clauses.append("timestamp >= %s")
            params.append(filters["since"])
        if filters.get("until"):
            clauses.append("timestamp <= %s")
            params.append(filters["until"])
        limit = filters.get("limit", 100)
        offset = filters.get("offset", 0)
        sql = (f"SELECT * FROM action_logs WHERE {' AND '.join(clauses)} "
               f"ORDER BY timestamp DESC LIMIT %s OFFSET %s")
        params.extend([limit, offset])
        rows = db_query(sql, tuple(params))
        return [_pg_row_to_entry(r) for r in rows]

    def count(self, ws_name: str, **filters) -> int:
        from engine.db import query_one
        clauses = ["workspace_name = %s"]
        params: list = [ws_name]
        for key in ("action_type", "actor_id", "outcome", "failure_type"):
            if filters.get(key):
                clauses.append(f"{key} = %s")
                params.append(filters[key])
        sql = f"SELECT COUNT(*) AS n FROM action_logs WHERE {' AND '.join(clauses)}"
        row = query_one(sql, tuple(params))
        return int(row["n"]) if row else 0


# ============ 辅助 ============

def _entry_to_dict(e: ActionLogEntry) -> dict:
    from dataclasses import asdict
    return asdict(e)


def _dict_to_entry(d: dict) -> ActionLogEntry:
    return ActionLogEntry(**d)


def _apply_filters(rows: list, filters: dict) -> list:
    """应用 action_type/actor_id/outcome/failure_type/since/until + 排序 + 分页。"""
    out = rows
    if filters.get("action_type"):
        out = [r for r in out if r.get("action_type") == filters["action_type"]]
    if filters.get("actor_id"):
        out = [r for r in out if r.get("actor_id") == filters["actor_id"]]
    if filters.get("outcome"):
        out = [r for r in out if r.get("outcome") == filters["outcome"]]
    if filters.get("failure_type"):
        out = [r for r in out if r.get("failure_type") == filters["failure_type"]]
    if filters.get("since"):
        out = [r for r in out if r.get("timestamp", "") >= filters["since"]]
    if filters.get("until"):
        out = [r for r in out if r.get("timestamp", "") <= filters["until"]]
    out.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    limit = filters.get("limit", 100)
    offset = filters.get("offset", 0)
    return out[offset:offset + limit]


def _pg_row_to_entry(row: dict) -> ActionLogEntry:
    """PG 行（psycopg 已解码 list/dict）转 ActionLogEntry。"""
    ts = row.get("timestamp")
    ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    return ActionLogEntry(
        log_id=row["log_id"], workspace_name=row["workspace_name"],
        timestamp=ts_str, action_type=row["action_type"], outcome=row["outcome"],
        failure_type=row.get("failure_type"), error_message=row.get("error_message"),
        actor_id=row.get("actor_id"), actor_role=row.get("actor_role"),
        actor_type=row["actor_type"], trigger_source=row["trigger_source"],
        edits_object_types=row.get("edits_object_types") or [],
        affected_objects=row.get("affected_objects") or {},
        params=row.get("params"), duration_ms=row.get("duration_ms"),
        llm_model=row.get("llm_model"), skill_id=row.get("skill_id"),
        session_id=row.get("session_id"),
    )


# ============ 工厂（spec §4.1）============

def build_action_log_repo(workspace_name: str,
                          data_dir: Optional[str] = None) -> ActionLogRepository:
    """PG 可用则 PgActionLogRepository，否则 JSONFileActionLogRepository。

    与 build_data_repository 同模式。JSON 后端需要 data_dir。
    """
    if is_pg_enabled() and ping():
        return PgActionLogRepository(workspace_name=workspace_name)
    if not data_dir:
        raise ValueError("JSON 后端需要 data_dir")
    return JSONFileActionLogRepository(data_dir=data_dir, workspace_name=workspace_name)
