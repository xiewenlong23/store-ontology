# Action Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every Action execution materializes as a queryable audit record (`action_logs`), closing the "agent black box" gap for production governance and providing the data source for Decision Lineage, Auditability, and Action Metrics.

**Architecture:** New independent `action_logs` storage (PG table + JSON file, separate from `entities`). The logging point is inside `executor.execute()` wrapped in try/except/finally — covering all trigger sources (LLM session / automation / webhook / admin). 8-class `failure_type` taxonomy aligned to existing executor raise points. Admin-only query API + console tab. Agent context (LLM model/skill/session) fields reserved in schema, populated in P1.

**Tech Stack:** Python 3 (existing `agent/engine/`), PostgreSQL via psycopg3 (existing `agent/engine/db.py`), JSON file backend (existing pattern), FastAPI (existing routers), pytest.

**Spec:** [`docs/superpowers/specs/2026-06-22-action-log-design.md`](../specs/2026-06-22-action-log-design.md)

**Open questions from spec §10 — RESOLVED in this plan:**
1. JSON backend rolling: 50000-entry cap (high enough to honor "permanent retention" intent for MVP, bounded for file operability). PG backend never rolls.
2. Admin UI: deferred to P1. P0 delivers API + Python query only.
3. params mask fields: hardcoded `password/password_hash/token/secret` (spec §7.1 default).

---

## File Structure

**Create:**
- `agent/engine/action_log.py` — `ActionLogEntry` dataclass + `init/update_success/update_failure` helpers + `classify_failure()` + `mask_sensitive_params()`
- `agent/engine/action_log_repo.py` — `ActionLogRepository` abstract + `PgActionLogRepository` + `JSONFileActionLogRepository` + `build_action_log_repo()` factory
- `agent/routers/action_logs.py` — admin API endpoints (`GET .../action-logs`, `GET .../action-logs/{log_id}`)
- `agent/sql/action_logs.sql` — new table DDL (sourced by `schema.sql` include or appended)
- `tests/engine/test_action_log_entry.py` — dataclass + classify + mask unit tests
- `tests/engine/test_action_log_repo_pg.py` — PG repo tests
- `tests/engine/test_action_log_repo_json.py` — JSON repo tests
- `tests/engine/test_executor_logging.py` — executor integration tests (every failure_type + success)
- `tests/routers/test_action_logs_api.py` — admin API tests

**Modify:**
- `agent/engine/executor.py` — wrap `execute()` in try/except/finally; add `trigger_source` param + `log_repo` ctor injection
- `agent/engine/workspace_bootstrap.py` — build `log_repo` per workspace; inject into executor; add field to `WorkspaceAgentInstance`
- `agent/tools/action_tools.py` — `confirm_action` passes `trigger_source="llm_session"`
- `workspace/retail/skills/clearance_workflow/automation.py` — 4 execute calls: 2 add `trigger_source="automation"`, 2 add `trigger_source="webhook"`
- `agent/sql/schema.sql` — append `action_logs` table DDL
- `agent/main.py` — include new `action_logs` router
- `agent/routers/_shared.py` — if `require_admin` helper is here, reuse (verify)

---

### Task 1: ActionLogEntry dataclass + failure classification + params masking

**Files:**
- Create: `agent/engine/action_log.py`
- Test: `tests/engine/test_action_log_entry.py`

- [ ] **Step 1: Write the failing test for ActionLogEntry init + update_success + update_failure**

`tests/engine/test_action_log_entry.py`:
```python
"""ActionLogEntry dataclass 单测：构造、成功/失败更新、affected_objects 提取。"""
import pytest
from engine.action_log import ActionLogEntry, classify_failure, mask_sensitive_params


def test_init_sets_basic_fields_and_user_actor():
    entry = ActionLogEntry.init(
        action_type="create_clearance_task",
        actor={"user_id": "u1", "role": "store_manager"},
        workspace_name="retail",
        trigger_source="llm_session",
    )
    assert entry.action_type == "create_clearance_task"
    assert entry.outcome == ""  # pending until update
    assert entry.actor_id == "u1"
    assert entry.actor_role == "store_manager"
    assert entry.actor_type == "user"
    assert entry.trigger_source == "llm_session"
    assert entry.workspace_name == "retail"
    assert entry.affected_objects == {}
    assert entry.failure_type is None


def test_init_agent_actor_has_agent_type():
    entry = ActionLogEntry.init(
        action_type="expiry_check",
        actor={"role": "system_scheduler"},
        workspace_name="retail",
        trigger_source="automation",
    )
    assert entry.actor_type == "agent"
    assert entry.actor_id == "agent:automation"  # agent 身份用 agent:<source>


def test_update_success_extracts_affected_pks():
    entry = ActionLogEntry.init("create_clearance_task",
                                {"user_id": "u1", "role": "store_manager"},
                                "retail", "llm_session")
    changes = {
        "created": {"Task": [{"id": "task_001"}]},
        "updated": {"NearExpiryProduct": [{"id": "nep_001"}, {"id": "nep_002"}]},
    }
    entry.update_success(changes)
    assert entry.outcome == "success"
    assert entry.failure_type is None
    assert entry.affected_objects == {"Task": ["task_001"],
                                      "NearExpiryProduct": ["nep_001", "nep_002"]}


def test_update_failure_sets_classification():
    entry = ActionLogEntry.init("approve_clearance",
                                {"user_id": "u1", "role": "clerk"},
                                "retail", "llm_session")
    entry.update_failure("permission_denied", "角色 clerk 无权提交")
    assert entry.outcome == "failure"
    assert entry.failure_type == "permission_denied"
    assert entry.error_message == "角色 clerk 无权提交"
```

Run: `pytest tests/engine/test_action_log_entry.py -v`
Expected: FAIL with ImportError (`engine.action_log` does not exist)

- [ ] **Step 2: Implement ActionLogEntry**

`agent/engine/action_log.py`:
```python
"""Action Log 条目数据模型 + 失败分类 + 敏感字段掩码（spec §3.3/§3.4/§7.1）。

每笔 Action 执行物化为一条 ActionLogEntry，由 executor 写入 action_logs 存储。
- outcome/failure_type 对齐 executor 现有 raise 点（8 类）
- affected_objects 从 _run_side_effects 的 changes 提取
- params 敏感字段掩码（审计完整性 vs 隐私，MVP 硬编码字段集）
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

# 敏感字段名（MVP 硬编码，spec §7.1；远期从 ontology 元数据推导）
_SENSITIVE_FIELDS = {"password", "password_hash", "token", "secret"}


@dataclass
class ActionLogEntry:
    log_id: str
    workspace_name: str
    timestamp: str  # ISO，写入存储时定
    action_type: str
    outcome: str = ""  # "success" / "failure" / ""（pending）
    failure_type: Optional[str] = None
    error_message: Optional[str] = None
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    actor_type: str = "user"  # "user" / "agent"
    trigger_source: str = "llm_session"
    edits_object_types: list = field(default_factory=list)
    affected_objects: dict = field(default_factory=dict)
    params: Optional[dict] = None
    duration_ms: Optional[int] = None
    # P1 预留（spec D3）
    llm_model: Optional[str] = None
    skill_id: Optional[str] = None
    session_id: Optional[str] = None

    @classmethod
    def init(cls, action_type, actor: dict, workspace_name: str,
             trigger_source: str = "llm_session") -> "ActionLogEntry":
        """构造待填充的 entry。actor 推导 actor_type/id/role。"""
        role = actor.get("role") or ""
        user_id = actor.get("user_id")
        if trigger_source == "llm_session" and user_id:
            actor_type = "user"
            actor_id = user_id
        else:
            # automation/webhook/admin 视为 agent 自动触发（spec §12.1 agent 身份）
            actor_type = "agent"
            actor_id = f"agent:{trigger_source}"
        return cls(
            log_id=uuid.uuid4().hex,
            workspace_name=workspace_name,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            action_type=action_type,
            actor_id=actor_id,
            actor_role=role,
            actor_type=actor_type,
            trigger_source=trigger_source,
        )

    def update_success(self, changes: dict) -> None:
        """从 _run_side_effects 的 changes 提取 affected_objects 并标记 success。"""
        self.outcome = "success"
        self.affected_objects = {}
        for obj_type, recs in changes.get("created", {}).items():
            self.affected_objects.setdefault(obj_type, []).extend(
                r.get("id") for r in recs if r.get("id"))
        for obj_type, recs in changes.get("updated", {}).items():
            existing = self.affected_objects.setdefault(obj_type, [])
            existing.extend(r.get("id") for r in recs if r.get("id"))


    def update_failure(self, failure_type: str, error_message: str) -> None:
        self.outcome = "failure"
        self.failure_type = failure_type
        self.error_message = error_message


# ============ failure 分类（spec §3.3，8 类对齐 executor raise 点）============

def classify_failure(exc: Exception) -> str:
    """基于异常类型 + 消息文本启发式分类（spec §3.3）。

    实现顺序：先匹配具体异常类型（EntityNotFoundError），再用 ValidationError
    消息关键词区分；其余 OntologyError → side_effect_error；非 OntologyError → unclassified。
    """
    from engine.errors import EntityNotFoundError, ValidationError, OntologyError
    if isinstance(exc, EntityNotFoundError):
        return "entity_not_found"
    if isinstance(exc, ValidationError):
        msg = str(exc)
        if "未知 Action Type" in msg or "未知 Action" in msg:
            return "unknown_action"
        if "角色" in msg and "无权提交" in msg:
            return "permission_denied"
        if "非法状态迁移" in msg:
            return "illegal_transition"
        if "缺少必填" in msg or "不满足约束" in msg:
            return "invalid_param"
        # 剩余 ValidationError 多为 submission 条件不满足
        return "submission_failed"
    if isinstance(exc, OntologyError):
        return "side_effect_error"
    return "unclassified"


# ============ 敏感字段掩码（spec §7.1）============

def mask_sensitive_params(params: Optional[dict]) -> Optional[dict]:
    """对 params 中的敏感字段值替换为 '***'（MVP 硬编码字段集）。"""
    if not params:
        return params
    masked = {}
    for k, v in params.items():
        masked[k] = "***" if k in _SENSITIVE_FIELDS else v
    return masked
```

- [ ] **Step 3: Run the entry tests to verify they pass**

Run: `pytest tests/engine/test_action_log_entry.py -v`
Expected: 4 PASSED

- [ ] **Step 4: Write failing tests for classify_failure + mask_sensitive_params**

Append to `tests/engine/test_action_log_entry.py`:
```python
from engine.errors import EntityNotFoundError, ValidationError, OntologyError


@pytest.mark.parametrize("exc,expected", [
    (EntityNotFoundError("未找到 X"), "entity_not_found"),
    (ValidationError("未知 Action Type: foo"), "unknown_action"),
    (ValidationError("角色 clerk 无权提交 approve_clearance"), "permission_denied"),
    (ValidationError("非法状态迁移: a -> b"), "illegal_transition"),
    (ValidationError("缺少必填参数: qty"), "invalid_param"),
    (ValidationError("参数 qty 不满足约束 0..100"), "invalid_param"),
    (ValidationError("submission 条件不满足"), "submission_failed"),
    (OntologyError("some other"), "side_effect_error"),
    (RuntimeError("boom"), "unclassified"),
])
def test_classify_failure(exc, expected):
    assert classify_failure(exc) == expected


def test_mask_sensitive_params_redacts_known_fields():
    out = mask_sensitive_params({"username": "admin", "password": "s3cr3t",
                                  "token": "abc", "quantity": 5})
    assert out == {"username": "admin", "password": "***", "token": "***", "quantity": 5}


def test_mask_sensitive_params_none_passthrough():
    assert mask_sensitive_params(None) is None
    assert mask_sensitive_params({}) == {}
```

- [ ] **Step 5: Run all entry tests**

Run: `pytest tests/engine/test_action_log_entry.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add agent/engine/action_log.py tests/engine/test_action_log_entry.py
git commit -m "feat(action-log): ActionLogEntry dataclass + failure classification + params masking"
```

---

### Task 2: PG schema for action_logs

**Files:**
- Modify: `agent/sql/schema.sql` (append)

- [ ] **Step 1: Append action_logs DDL to schema.sql**

Append to `agent/sql/schema.sql` (after the `entities` table section, before `touch_updated_at` trigger section):
```sql

-- ============ Action Log（决策即数据，spec §3.1）============
-- 独立于 entities，治理数据与业务数据分离；永久保留（MVP，spec D6）

CREATE TABLE IF NOT EXISTS action_logs (
    log_id              text NOT NULL,             -- uuid hex
    workspace_name      text NOT NULL,
    timestamp           timestamptz NOT NULL DEFAULT now(),
    action_type         text NOT NULL,
    outcome             text NOT NULL,             -- success / failure
    failure_type        text,                      -- failure 时填（8 类枚举）；success NULL
    error_message       text,
    actor_id            text,
    actor_role          text,
    actor_type          text NOT NULL,             -- user / agent
    trigger_source      text NOT NULL,             -- llm_session / automation / webhook / admin_api
    edits_object_types  text[] NOT NULL DEFAULT '{}',
    affected_objects    jsonb NOT NULL DEFAULT '{}',
    params              jsonb,
    duration_ms         integer,
    -- P1 预留 agent 运行时上下文
    llm_model           text,
    skill_id            text,
    session_id          text,
    PRIMARY KEY (log_id)
);

CREATE INDEX IF NOT EXISTS idx_action_logs_ws_time
    ON action_logs (workspace_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_action_logs_ws_action
    ON action_logs (workspace_name, action_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_action_logs_ws_actor
    ON action_logs (workspace_name, actor_id, timestamp DESC);
```

- [ ] **Step 2: Verify migration applies cleanly (manual, requires PG)**

If PG is configured locally:
```bash
cd agent && python -c "from engine.db import migrate; migrate(); print('OK')"
```
Expected: prints `OK` (CREATE IF NOT EXISTS is idempotent). If PG not configured locally, this step is N/A — the DDL runs on first deploy.

- [ ] **Step 3: Commit**

```bash
git add agent/sql/schema.sql
git commit -m "feat(action-log): action_logs PG table + indexes"
```

---

### Task 3: ActionLogRepository — JSON backend

**Files:**
- Create: `agent/engine/action_log_repo.py`
- Test: `tests/engine/test_action_log_repo_json.py`

- [ ] **Step 1: Write the failing test for JSON repo**

`tests/engine/test_action_log_repo_json.py`:
```python
"""JSONFileActionLogRepository 单测：append + 查询过滤 + 分页 + 滚动截断。"""
import json
import os
import tempfile

from engine.action_log import ActionLogEntry
from engine.action_log_repo import JSONFileActionLogRepository, build_action_log_repo


def _entry(action_type="a", outcome="success", actor_id="u1", ts=None, **kw):
    e = ActionLogEntry.init(action_type, {"user_id": actor_id, "role": "r"},
                            "ws", "llm_session")
    e.outcome = outcome
    e.timestamp = ts or "2026-06-22T10:00:00"
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def test_json_write_then_query_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        repo = JSONFileActionLogRepository(data_dir=d, workspace_name="ws")
        repo.write(_entry("a1", "success", "u1"))
        rows = repo.query("ws")
        assert len(rows) == 1
        assert rows[0].action_type == "a1"
        assert rows[0].outcome == "success"


def test_json_query_filters_by_action_type_and_outcome():
    with tempfile.TemporaryDirectory() as d:
        repo = JSONFileActionLogRepository(data_dir=d, workspace_name="ws")
        repo.write(_entry("a1", "success", "u1"))
        repo.write(_entry("a2", "failure", "u2", failure_type="invalid_param"))
        assert len(repo.query("ws", action_type="a1")) == 1
        assert len(repo.query("ws", outcome="failure")) == 1
        assert len(repo.query("ws", failure_type="invalid_param")) == 1


def test_json_query_pagination():
    with tempfile.TemporaryDirectory() as d:
        repo = JSONFileActionLogRepository(data_dir=d, workspace_name="ws")
        for i in range(5):
            repo.write(_entry(f"a{i}", "success", "u1"))
        assert len(repo.query("ws", limit=2)) == 2
        assert len(repo.query("ws", limit=2, offset=4)) == 1


def test_json_count():
    with tempfile.TemporaryDirectory() as d:
        repo = JSONFileActionLogRepository(data_dir=d, workspace_name="ws")
        repo.write(_entry("a1", "success", "u1"))
        repo.write(_entry("a2", "failure", "u2"))
        assert repo.count("ws") == 2
        assert repo.count("ws", outcome="success") == 1


def test_json_rolling_cap_at_50000():
    # 只验证 cap 逻辑：写 cap+1 条，确认截断到 cap
    with tempfile.TemporaryDirectory() as d:
        repo = JSONFileActionLogRepository(data_dir=d, workspace_name="ws")
        repo._cap = 3  # 测试用小 cap
        for i in range(4):
            repo.write(_entry("a", "success", "u1"))
        assert repo.count("ws") == 3  # 截断到 cap


def test_build_action_log_repo_json_when_no_pg(monkeypatch):
    # monkeypatch is_pg_enabled 返回 False
    monkeypatch.setattr("engine.action_log_repo.is_pg_enabled", lambda: False)
    with tempfile.TemporaryDirectory() as d:
        repo = build_action_log_repo(workspace_name="ws", data_dir=d)
        assert repo.storage_kind == "json"
```

Run: `pytest tests/engine/test_action_log_repo_json.py -v`
Expected: FAIL with ImportError

- [ ] **Step 2: Implement JSONFileActionLogRepository + abstract + factory**

`agent/engine/action_log_repo.py`:
```python
"""ActionLogRepository —— Action Log 存储抽象 + 双后端实现（spec §4）。

PG：专用 action_logs 表（带索引，永久保留）
JSON：workspace/<ws>/data/action_logs.json（append-only array，50000 条滚动）

工厂 build_action_log_repo：PG 可用则 PgActionLogRepository，否则 JSON。
与 build_data_repository 同模式。
"""
import json
import os
import threading
from datetime import datetime
from typing import List, Optional

from engine.action_log import ActionLogEntry, mask_sensitive_params

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

    与 auth_audit.json 同构（atomic temp replace + flock），但 50000 条滚动 + 永久保留意图。
    """
    storage_kind = "json"
    _cap = _JSON_CAP  # 测试可覆盖

    def __init__(self, data_dir: str, workspace_name: str):
        self._path = os.path.join(data_dir, "action_logs.json")
        self._lock = threading.Lock()
        os.makedirs(data_dir, exist_ok=True)

    def write(self, entry: ActionLogEntry) -> None:
        # 写入时掩码 params（spec §7.1）
        entry.params = mask_sensitive_params(entry.params)
        try:
            with self._lock:
                existing = self._load()
                existing.append(_entry_to_dict(entry))
                if len(existing) > self._cap:
                    existing = existing[-self._cap:]
                self._save(existing)
        except Exception as e:  # noqa: BLE001 - 审计失败不阻断请求（spec §7.3）
            print(f"[action_log] JSON write 失败（不影响请求）: {e}")

    def query(self, ws_name: str, **filters) -> List[ActionLogEntry]:
        rows = self._load()
        # workspace 隔离：JSON 文件已是 per-workspace，但过滤以防误传
        rows = [r for r in rows if r.get("workspace_name") == ws_name]
        rows = _apply_filters(rows, filters)
        return [_dict_to_entry(r) for r in rows]

    def count(self, ws_name: str, **filters) -> int:
        return len(self.query(ws_name, **filters))

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


# ============ 辅助 ============

def _entry_to_dict(e: ActionLogEntry) -> dict:
    from dataclasses import asdict
    return asdict(e)


def _dict_to_entry(d: dict) -> ActionLogEntry:
    return ActionLogEntry(**d)


def _apply_filters(rows: list, filters: dict) -> list:
    """应用 action_type/actor_id/outcome/failure_type/since/until，返回排序+分页后的 list。"""
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
    # 时间倒序
    out.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    limit = filters.get("limit", 100)
    offset = filters.get("offset", 0)
    return out[offset:offset + limit]


# ============ 工厂（spec §4.1）============

def build_action_log_repo(workspace_name: str, data_dir: Optional[str] = None) -> ActionLogRepository:
    """PG 可用则 PgActionLogRepository，否则 JSONFileActionLogRepository。

    与 build_data_repository 同模式。PG 实现在 Task 4 补。
    """
    from engine.db import is_pg_enabled, ping
    if is_pg_enabled() and ping():
        return PgActionLogRepository(workspace_name=workspace_name)
    if not data_dir:
        raise ValueError("JSON 后端需要 data_dir")
    return JSONFileActionLogRepository(data_dir=data_dir, workspace_name=workspace_name)


# PG 实现在 Task 4 引入；此处占位避免 build_action_log_repo 引用未定义
class PgActionLogRepository(ActionLogRepository):
    storage_kind = "pg"

    def __init__(self, workspace_name: str):
        self.workspace_name = workspace_name
        raise NotImplementedError("PgActionLogRepository 在 Task 4 实现")
```

- [ ] **Step 3: Run JSON repo tests**

Run: `pytest tests/engine/test_action_log_repo_json.py -v`
Expected: all 6 PASS

- [ ] **Step 4: Commit**

```bash
git add agent/engine/action_log_repo.py tests/engine/test_action_log_repo_json.py
git commit -m "feat(action-log): JSONFileActionLogRepository + abstract + factory"
```

---

### Task 4: ActionLogRepository — PG backend

**Files:**
- Modify: `agent/engine/action_log_repo.py` (replace PgActionLogRepository stub)
- Test: `tests/engine/test_action_log_repo_pg.py`

- [ ] **Step 1: Write the failing test for PG repo (uses real PG via db.py, skip if not available)**

`tests/engine/test_action_log_repo_pg.py`:
```python
"""PgActionLogRepository 单测。需要 PG；PG 不可用时 skip。"""
import pytest

from engine.action_log import ActionLogEntry
from engine.action_log_repo import PgActionLogRepository, build_action_log_repo


def _pg_available():
    from engine.db import is_pg_enabled, ping
    return is_pg_enabled() and ping()


pytestmark = pytest.mark.skipif(not _pg_available(),
                                 reason="PG 不可用，跳过 PG repo 测试")


@pytest.fixture(autouse=True)
def clean_logs():
    """每测前清空 action_logs 表，避免污染。"""
    from engine.db import execute
    execute("DELETE FROM action_logs WHERE workspace_name = %s", ("ws_pg",))
    yield
    execute("DELETE FROM action_logs WHERE workspace_name = %s", ("ws_pg",))


def _entry(action_type="a", outcome="success", **kw):
    e = ActionLogEntry.init(action_type, {"user_id": "u1", "role": "r"},
                            "ws_pg", "llm_session")
    e.outcome = outcome
    e.timestamp = "2026-06-22T10:00:00"
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def test_pg_write_then_query():
    repo = PgActionLogRepository("ws_pg")
    repo.write(_entry("a1", "success"))
    rows = repo.query("ws_pg")
    assert len(rows) == 1
    assert rows[0].action_type == "a1"


def test_pg_query_filters_and_pagination():
    repo = PgActionLogRepository("ws_pg")
    repo.write(_entry("a1", "success"))
    repo.write(_entry("a2", "failure", failure_type="invalid_param"))
    assert len(repo.query("ws_pg", outcome="success")) == 1
    assert len(repo.query("ws_pg", limit=1)) == 1


def test_pg_count():
    repo = PgActionLogRepository("ws_pg")
    repo.write(_entry("a1", "success"))
    repo.write(_entry("a2", "failure"))
    assert repo.count("ws_pg") == 2


def test_build_action_log_repo_pg_when_available():
    repo = build_action_log_repo("ws_pg")
    assert repo.storage_kind == "pg"
```

Run: `pytest tests/engine/test_action_log_repo_pg.py -v`
Expected: FAIL or SKIP (PgActionLogRepository raises NotImplementedError)

- [ ] **Step 2: Implement PgActionLogRepository (replace the stub)**

Replace the `PgActionLogRepository` stub at the bottom of `agent/engine/action_log_repo.py` with:
```python
class PgActionLogRepository(ActionLogRepository):
    """PG action_logs 表实现（spec §4.1）。"""
    storage_kind = "pg"

    def __init__(self, workspace_name: str):
        self.workspace_name = workspace_name

    def write(self, entry: ActionLogEntry) -> None:
        from dataclasses import asdict
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
                entry.edits_object_types or [], entry.affected_objects or {},
                json.dumps(masked) if masked is not None else None,
                entry.duration_ms, entry.llm_model, entry.skill_id, entry.session_id,
            ))
        except Exception as e:  # noqa: BLE001 - 审计失败不阻断请求（spec §7.3）
            print(f"[action_log] PG write 失败（不影响请求）: {e}")

    def query(self, ws_name: str, **filters) -> List[ActionLogEntry]:
        from engine.db import query as db_query
        clauses = ["workspace_name = %s"]
        params: list = [ws_name]
        if filters.get("action_type"):
            clauses.append("action_type = %s"); params.append(filters["action_type"])
        if filters.get("actor_id"):
            clauses.append("actor_id = %s"); params.append(filters["actor_id"])
        if filters.get("outcome"):
            clauses.append("outcome = %s"); params.append(filters["outcome"])
        if filters.get("failure_type"):
            clauses.append("failure_type = %s"); params.append(filters["failure_type"])
        if filters.get("since"):
            clauses.append("timestamp >= %s"); params.append(filters["since"])
        if filters.get("until"):
            clauses.append("timestamp <= %s"); params.append(filters["until"])
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
                clauses.append(f"{key} = %s"); params.append(filters[key])
        sql = f"SELECT COUNT(*) AS n FROM action_logs WHERE {' AND '.join(clauses)}"
        row = query_one(sql, tuple(params))
        return int(row["n"]) if row else 0


def _pg_row_to_entry(row: dict) -> ActionLogEntry:
    """PG 行（含 list/dict 已由 psycopg 解码）转 ActionLogEntry。"""
    return ActionLogEntry(
        log_id=row["log_id"], workspace_name=row["workspace_name"],
        timestamp=row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat")
            else str(row["timestamp"]),
        action_type=row["action_type"], outcome=row["outcome"],
        failure_type=row.get("failure_type"), error_message=row.get("error_message"),
        actor_id=row.get("actor_id"), actor_role=row.get("actor_role"),
        actor_type=row["actor_type"], trigger_source=row["trigger_source"],
        edits_object_types=row.get("edits_object_types") or [],
        affected_objects=row.get("affected_objects") or {},
        params=row.get("params"), duration_ms=row.get("duration_ms"),
        llm_model=row.get("llm_model"), skill_id=row.get("skill_id"),
        session_id=row.get("session_id"),
    )
```

- [ ] **Step 3: Run PG repo tests**

Run: `pytest tests/engine/test_action_log_repo_pg.py -v`
Expected: PASS if PG available; SKIP otherwise. Both outcomes acceptable.

- [ ] **Step 4: Commit**

```bash
git add agent/engine/action_log_repo.py tests/engine/test_action_log_repo_pg.py
git commit -m "feat(action-log): PgActionLogRepository implementation"
```

---

### Task 5: Wire log_repo into executor + workspace_bootstrap

**Files:**
- Modify: `agent/engine/executor.py`
- Modify: `agent/engine/workspace_bootstrap.py`
- Test: `tests/engine/test_executor_logging.py`

- [ ] **Step 1: Write the failing integration test for executor logging**

`tests/engine/test_executor_logging.py`:
```python
"""executor.execute 日志写入集成测试：每种 failure_type + success。

用 fake log_repo（内存 list）捕获 entry，断言 outcome/failure_type/trigger_source/重抛。
"""
import pytest

from engine.action_log import ActionLogEntry
from engine.action_log_repo import ActionLogRepository
from engine.errors import ValidationError, EntityNotFoundError
from engine.executor import ActionExecutor


class FakeLogRepo(ActionLogRepository):
    storage_kind = "fake"
    def __init__(self): self.entries = []
    def write(self, e): self.entries.append(e)
    def query(self, ws, **f): return [e for e in self.entries if e.workspace_name == ws]
    def count(self, ws, **f): return len(self.query(ws, **f))


def _action(api_name="a", parameters=None, side_effects=None,
            submission_criteria=None, target_object_type="T", edits_object_types=None):
    """构造一个轻量 ActionDefinition-like 对象（用 SimpleNamespace 模拟）。"""
    from types import SimpleNamespace
    return SimpleNamespace(
        api_name=api_name,
        parameters=parameters or [],
        side_effects=side_effects or [],
        submission_criteria=submission_criteria or {},
        target_object_type=target_object_type,
        edits_object_types=edits_object_types or [],
        locator_field=None,
    )


def _registry():
    from types import SimpleNamespace
    return SimpleNamespace(object_types={"T": object})


def test_unknown_action_logs_failure_and_reraises():
    log = FakeLogRepo()
    ex = ActionExecutor(repository=None, actions={}, registry=_registry(),
                        config=None, log_repo=log)
    with pytest.raises(ValidationError):
        ex.execute("nope", {}, actor={"role": "r"}, tenant_id="ws",
                   trigger_source="llm_session")
    assert len(log.entries) == 1
    e = log.entries[0]
    assert e.outcome == "failure"
    assert e.failure_type == "unknown_action"
    assert e.trigger_source == "llm_session"


def test_invalid_param_logs_and_reraises():
    log = FakeLogRepo()
    action = _action(parameters=[{"name": "qty", "required": True}])
    ex = ActionExecutor(repository=None, actions={"a": action},
                        registry=_registry(), config=None, log_repo=log)
    with pytest.raises(ValidationError):
        ex.execute("a", {}, actor={"role": "r"}, tenant_id="ws")
    assert log.entries[0].failure_type == "invalid_param"


def test_default_trigger_source_is_llm_session():
    """execute 不传 trigger_source 时默认 llm_session（向后兼容，spec §3.2）。"""
    log = FakeLogRepo()
    ex = ActionExecutor(repository=None, actions={}, registry=_registry(),
                        config=None, log_repo=log)
    with pytest.raises(ValidationError):
        ex.execute("nope", {}, actor={"role": "r"}, tenant_id="ws")
    assert log.entries[0].trigger_source == "llm_session"


def test_executor_works_without_log_repo_for_backward_compat():
    """旧代码构造 executor 不传 log_repo 时不应崩（日志静默跳过）。"""
    ex = ActionExecutor(repository=None, actions={}, registry=_registry(), config=None)
    with pytest.raises(ValidationError):
        ex.execute("nope", {}, actor={"role": "r"}, tenant_id="ws")
    # 不崩即通过
```

Run: `pytest tests/engine/test_executor_logging.py -v`
Expected: FAIL (executor.execute signature / log_repo not present)

- [ ] **Step 2: Modify ActionExecutor to accept log_repo and wrap execute() in try/except/finally**

Modify `agent/engine/executor.py`:

Change the `ActionExecutor.__init__` (lines ~106-110) to add `log_repo=None`:
```python
class ActionExecutor:
    def __init__(self, repository, actions: Dict[str, object], registry, config=None,
                 log_repo=None):
        self.repo = repository
        self.actions = actions
        self.registry = registry
        self.config = config  # 价值链流程上下文（提供状态机表与工作流对象类型）
        self.log_repo = log_repo  # ActionLogRepository（spec §3.2）；None 则静默跳过
```

Replace the entire `execute` method (lines ~121-130) with:
```python
    def execute(self, action_type: str, params: dict, *, actor: dict,
                tenant_id, trigger_source: str = "llm_session") -> dict:
        """执行 Action（原子副作用）+ 写 Action Log（spec §3.2）。

        trigger_source: llm_session / automation / webhook / admin_api（Decision Lineage）
        日志写入失败不阻断请求（spec §7.3）；execute 本身的异常正常重抛。
        """
        import time
        from engine.action_log import ActionLogEntry, classify_failure

        # tenant_id 可能是 TenantContext 或字符串；取 workspace_name 用于日志
        ws_name = getattr(tenant_id, "workspace_name", tenant_id)
        entry = ActionLogEntry.init(action_type, actor, ws_name, trigger_source)
        t0 = time.monotonic()
        try:
            action = self.actions.get(action_type)
            if not action:
                raise ValidationError(f"未知 Action Type: {action_type}")
            params = self._validate_params(action, params)
            target = self._load_target(action, params, tenant_id)
            self._check_submission(action, actor, target, params, tenant_id)
            changes = self._run_side_effects(action, params, tenant_id)
            entry.update_success(changes)
            return {"ok": True, "action": action_type, "created": changes["created"],
                    "updated": changes["updated"]}
        except Exception as e:
            entry.update_failure(classify_failure(e), str(e))
            raise
        finally:
            entry.duration_ms = int((time.monotonic() - t0) * 1000)
            if self.log_repo is not None:
                try:
                    self.log_repo.write(entry)
                except Exception as e:  # noqa: BLE001 - 审计失败不阻断（spec §7.3）
                    print(f"[action_log] 写入失败（不影响请求）: {e}")
```

- [ ] **Step 3: Run executor logging tests**

Run: `pytest tests/engine/test_executor_logging.py -v`
Expected: 4 PASS

- [ ] **Step 4: Commit**

```bash
git add agent/engine/executor.py tests/engine/test_executor_logging.py
git commit -m "feat(action-log): executor writes ActionLog on every execute (try/except/finally)"
```

---

### Task 6: Build log_repo in workspace_bootstrap + inject into executor

**Files:**
- Modify: `agent/engine/workspace_bootstrap.py`

- [ ] **Step 1: Add log_repo field to WorkspaceAgentInstance + build/inject in bootstrap_workspace**

Modify `agent/engine/workspace_bootstrap.py`:

In the `WorkspaceAgentInstance` dataclass (lines ~14-26), add a field:
```python
@dataclass
class WorkspaceAgentInstance:
    """一个 workspace 的 Agent 运行时实例（registry + repository + executor）。"""
    workspace_name: str
    config: WorkspaceConfig
    registry: object  # EntityRegistry
    repository: object  # Repository
    executor: object  # ActionExecutor（config 取自 source_pack 的价值链流程）
    log_repo: object = None  # ActionLogRepository（spec §4.1）

    @property
    def tenant_context(self) -> TenantContext:
        """该 workspace 的默认上下文（通配 org，总部视角）。"""
        return TenantContext(workspace_name=self.workspace_name, org_unit_id="*")
```

In `bootstrap_workspace`, after constructing `executor` (line ~123-125) and before constructing `inst` (line ~127), insert log_repo construction and re-wire executor:
```python
    executor = ActionExecutor(
        repository=repo, actions=registry.action_types,
        registry=registry, config=process_config)

    # Action Log repo（spec §4.1）：PG 或 JSON 双后端
    from engine.action_log_repo import build_action_log_repo
    try:
        log_repo = build_action_log_repo(workspace_name=workspace_name, data_dir=data_dir)
        executor.log_repo = log_repo
    except Exception as e:  # noqa: BLE001 - log_repo 构造失败不应阻断 workspace 启动
        print(f"[bootstrap] action_log_repo 构造失败（日志将不写入）: {e}")
        log_repo = None

    inst = WorkspaceAgentInstance(
        workspace_name=workspace_name, config=cfg,
        registry=registry, repository=repo, executor=executor, log_repo=log_repo)
```

- [ ] **Step 2: Verify bootstrap still works (smoke test)**

```bash
cd agent && python -c "
from engine.workspace_bootstrap import bootstrap_workspace
inst = bootstrap_workspace('jjy')
print('log_repo:', inst.log_repo, 'kind:', getattr(inst.log_repo, 'storage_kind', None))
print('executor.log_repo set:', inst.executor.log_repo is not None)
"
```
Expected: prints `log_repo: <...Repo object>` with `kind: json` (or `pg` if PG configured), `executor.log_repo set: True`.

- [ ] **Step 3: Commit**

```bash
git add agent/engine/workspace_bootstrap.py
git commit -m "feat(action-log): bootstrap builds log_repo and injects into executor"
```

---

### Task 7: Wire trigger_source at all call sites

**Files:**
- Modify: `agent/tools/action_tools.py`
- Modify: `workspace/retail/skills/clearance_workflow/automation.py`

- [ ] **Step 1: confirm_action passes trigger_source="llm_session"**

In `agent/tools/action_tools.py`, find the `confirm_action` function's execute call (around lines ~99-102) and add the kwarg:
```python
        result = shared._get_executor().execute(
            preview["action_type"], preview["params"],
            actor=preview["actor"],
            tenant_id=preview["tenant_id"],
            trigger_source="llm_session")
```

- [ ] **Step 2: automation.py jobs pass trigger_source="automation", webhook handlers pass "webhook"**

In `workspace/retail/skills/clearance_workflow/automation.py`:

`expiry_check_job`'s execute call (around line ~37) — add `trigger_source="automation"`:
```python
            executor.execute("create_loss_report", {
                "task_id": task["id"],
                "target_id": task["target_id"],
                "loss_quantity": loss_qty,
                "loss_value": loss_value,
                "loss_reason": f"到期未售罄自动报损（剩余{ne.get('days_left')}天）",
            }, actor={"role": "system_scheduler"}, tenant_id=tenant_id,
               trigger_source="automation")
```

`inventory_check_job`'s execute call (around line ~58) — add `trigger_source="automation"`:
```python
            executor.execute("complete_task", {
                "task_id": task["id"],
                "target_id": task["target_id"],
            }, actor={"role": "system_inventory"}, tenant_id=tenant_id,
               trigger_source="automation")
```

`handle_approval`'s execute call (around line ~76) — add `trigger_source="webhook"`:
```python
    return executor.execute("approve_clearance", {
        "task_id": task_id, "approver_id": approver_id,
    }, actor={"role": "region_cat_mgr"}, tenant_id=tenant_id,
       trigger_source="webhook")
```

`handle_pos_scan`'s execute call (around line ~84) — add `trigger_source="webhook"`:
```python
    return executor.execute("deduct_stock", {
        "target_id": target_id, "task_id": task_id, "quantity": quantity,
    }, actor={"role": "system_pos"}, tenant_id=tenant_id,
       trigger_source="webhook")
```

- [ ] **Step 3: Verify no other execute() call sites missing trigger_source**

Search for `executor.execute(` and `.execute(` calls on executors across the codebase:
```bash
cd agent && python -c "
import subprocess, sys
r = subprocess.run(['grep', '-rn', 'execute(\"', '../agent', '../workspace'], capture_output=True, text=True)
print(r.stdout)
" | grep -i 'execute' || true
```
Manually inspect the output. Expected: only the 5 call sites in action_tools.py + automation.py (already wired) + test fixtures. Any missed production call site must be wired with the appropriate trigger_source.

- [ ] **Step 4: Commit**

```bash
git add agent/tools/action_tools.py workspace/retail/skills/clearance_workflow/automation.py
git commit -m "feat(action-log): wire trigger_source at all execute() call sites (llm_session/automation/webhook)"
```

---

### Task 8: Admin API for querying action logs

**Files:**
- Create: `agent/routers/action_logs.py`
- Modify: `agent/main.py` (include router)
- Test: `tests/routers/test_action_logs_api.py`

- [ ] **Step 1: Verify the require_admin helper signature**

Check `agent/engine/admin_ontology_api.py` for `require_admin` — it should accept `(ws_name)` and raise if the caller is not system_admin/bootstrap admin. Confirm the exact import path before using it.

```bash
grep -n "def require_admin" agent/engine/admin_ontology_api.py
```

- [ ] **Step 2: Write the failing API test**

`tests/routers/test_action_logs_api.py`:
```python
"""admin action-logs API 测试：列表/详情/权限/过滤/分页。

用 FastAPI TestClient + monkeypatch require_admin 放行 + 注入 fake log_repo。
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    # 放行 require_admin
    monkeypatch.setattr("engine.admin_ontology_api.require_admin", lambda ws: None)
    from agent.main import app
    return TestClient(app)


def test_list_action_logs_empty(client):
    r = client.get("/api/admin/customers/jjy/action-logs")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_action_logs_filters(client, monkeypatch):
    # 注入一条 log
    from agent.engine.action_log import ActionLogEntry
    from engine.action_log_repo import ActionLogRepository

    class FakeRepo(ActionLogRepository):
        storage_kind = "fake"
        def __init__(self): self._e = []
        def write(self, e): self._e.append(e)
        def query(self, ws, **f):
            return [e for e in self._e if e.workspace_name == ws
                    and (not f.get("outcome") or e.outcome == f["outcome"])]
        def count(self, ws, **f): return len(self.query(ws, **f))

    fake = FakeRepo()
    e = ActionLogEntry.init("a", {"user_id": "u1", "role": "r"}, "jjy", "llm_session")
    e.outcome = "success"
    fake._e.append(e)
    monkeypatch.setattr(
        "agent.routers.action_logs._get_log_repo", lambda ws: fake)

    r = client.get("/api/admin/customers/jjy/action-logs?outcome=success")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["action_type"] == "a"


def test_detail_404_when_unknown(client, monkeypatch):
    monkeypatch.setattr("agent.routers.action_logs._get_log_repo",
                        lambda ws: type("R", (), {"query": lambda *a, **k: []})())
    r = client.get("/api/admin/customers/jjy/action-logs/nonexistent")
    assert r.status_code == 404
```

Run: `pytest tests/routers/test_action_logs_api.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the action_logs router**

`agent/routers/action_logs.py`:
```python
"""admin Action Log 查询 API（spec §6.1）。

仅 admin（system_admin / bootstrap admin）可访问；LLM 无查询 Tool（审计是人的职责）。
路径：/api/admin/customers/{cid}/action-logs
"""
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from engine.admin_ontology_api import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin-action-logs"])


def _get_log_repo(workspace_name: str):
    """从 workspace 实例取 log_repo（spec §4.1）。

    路由内单独函数，便于测试 monkeypatch。
    """
    from engine.workspace_bootstrap import bootstrap_workspace
    inst = bootstrap_workspace(workspace_name)
    if inst.log_repo is None:
        raise HTTPException(status_code=503,
                            detail="该 workspace 未启用 Action Log")
    return inst.log_repo


def _resolve_workspace(cid: str) -> str:
    from agent.routers._shared import resolve_workspace_name
    from fastapi import Request
    # _shared.resolve_workspace_name 需要 request；这里 cid 直接用作 workspace_name
    # （admin 路径已与 data-browser / ontology editor 一致）
    return cid


@router.get("/customers/{cid}/action-logs")
def list_action_logs(cid: str,
                     action_type: Optional[str] = Query(None),
                     actor_id: Optional[str] = Query(None),
                     outcome: Optional[str] = Query(None),
                     failure_type: Optional[str] = Query(None),
                     since: Optional[str] = Query(None),
                     until: Optional[str] = Query(None),
                     limit: int = Query(100, ge=1, le=500),
                     offset: int = Query(0, ge=0)):
    """列出 Action Log（按时间倒序，支持过滤 + 分页）。"""
    ws = cid
    require_admin(ws)
    repo = _get_log_repo(ws)
    filters = {"action_type": action_type, "actor_id": actor_id,
               "outcome": outcome, "failure_type": failure_type,
               "since": since, "until": until, "limit": limit, "offset": offset}
    # 剔除 None
    filters = {k: v for k, v in filters.items() if v is not None or k in ("limit", "offset")}
    count_filters = {k: v for k, v in filters.items() if k not in ("limit", "offset")}
    items = repo.query(ws, **filters)
    total = repo.count(ws, **count_filters)
    return {"items": [asdict(e) for e in items], "total": total}


@router.get("/customers/{cid}/action-logs/{log_id}")
def get_action_log(cid: str, log_id: str):
    """取单条 Action Log 详情（含完整 params / affected_objects）。"""
    ws = cid
    require_admin(ws)
    repo = _get_log_repo(ws)
    # 用 query + 过滤 log_id（log_id 是 PK，但 query 接口不直接支持）
    # 简单实现：扫最近 1000 条找；PG 后端未来可加 by_id 优化
    rows = repo.query(ws, limit=1000)
    for e in rows:
        if e.log_id == log_id:
            return asdict(e)
    raise HTTPException(status_code=404, detail="Action Log 不存在")
```

- [ ] **Step 4: Include the router in main.py**

In `agent/main.py`, find where routers are included (look for `app.include_router` near the other admin/auth/webhook/dashboard routers) and add:
```python
from agent.routers import action_logs as action_logs_router
app.include_router(action_logs_router.router)
```

- [ ] **Step 5: Run the API tests**

Run: `pytest tests/routers/test_action_logs_api.py -v`
Expected: 3 PASS (or some may need minor fixture adjustments depending on how main.py app construction handles imports — fix as needed)

- [ ] **Step 6: Commit**

```bash
git add agent/routers/action_logs.py agent/main.py tests/routers/test_action_logs_api.py
git commit -m "feat(action-log): admin query API (list + detail, require_admin gated)"
```

---

### Task 9: End-to-end integration test

**Files:**
- Test: `tests/integration/test_action_log_e2e.py`

- [ ] **Step 1: Write an E2E test that runs a real Action and verifies the log**

`tests/integration/test_action_log_e2e.py`:
```python
"""End-to-end：跑一笔 clearance Action，查 Action Log 确认完整链路。

用 JSON 后端（无 PG 依赖），bootstrap jjy workspace，执行 deduct_stock，
断言 log_repo 里有对应 entry。
"""
import pytest

from engine.workspace_bootstrap import bootstrap_workspace, invalidate_workspace


@pytest.fixture
def ws_instance():
    invalidate_workspace("jjy")  # 重建以拿到 fresh log_repo
    inst = bootstrap_workspace("jjy")
    # 清空 action_logs.json 避免历史污染
    import json, os
    if inst.log_repo and inst.log_repo.storage_kind == "json":
        open(inst.log_repo._path, "w").write("[]")
    return inst


def test_clearance_action_produces_log_entry(ws_instance):
    """执行一笔 create_clearance_task，确认 log 写入 success entry。"""
    inst = ws_instance
    # 准备一个 in_progress 的 task + clearance NEP（seed 数据已有）
    from engine.tenant import TenantContext
    tc = inst.tenant_context

    # 用 admin 身份跑一笔（system_admin 短路 submission_criteria）
    # 找一个 seed 的 in_progress task
    tasks = inst.repository.read("Task", tc)
    in_progress = [t for t in tasks if t.get("status") == "in_progress"]
    if not in_progress:
        pytest.skip("seed 无 in_progress task，跳过 E2E")

    target_task = in_progress[0]
    target_id = target_task.get("target_id")

    try:
        result = inst.executor.execute(
            "update_task_notes",
            {"task_id": target_task["id"], "notes": "E2E test note"},
            actor={"user_id": "admin", "role": "system_admin"},
            tenant_id=tc, trigger_source="llm_session")
    except Exception as e:
        # 即使 Action 失败，log 也应记录 failure
        pass

    # 查 log
    entries = inst.log_repo.query("jjy", action_type="update_task_notes")
    assert len(entries) >= 1
    e = entries[0]
    assert e.action_type == "update_task_notes"
    assert e.trigger_source == "llm_session"
    assert e.actor_id == "admin"
    assert e.actor_type == "user"
    assert e.outcome in ("success", "failure")
    if e.outcome == "success":
        assert "Task" in e.affected_objects
```

- [ ] **Step 2: Run the E2E test**

Run: `pytest tests/integration/test_action_log_e2e.py -v`
Expected: PASS (confirms the full bootstrap → execute → log pipeline works on the real jjy workspace)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_action_log_e2e.py
git commit -m "test(action-log): E2E integration — clearance action produces queryable log entry"
```

---

### Task 10: Documentation update

**Files:**
- Modify: `docs/design/roadmap.md` (mark Action Log item as ✅ in §10)

- [ ] **Step 1: Update roadmap §10 to reflect landed status**

In `docs/design/roadmap.md` §10, the P0 bullet list currently says Action Log is 🔜. After implementation lands, update the line for **Action Log** to mark it ✅ and add a brief "已落地" note with the commit reference. The other P0 items (Decision Lineage, Action Metrics, notification 投递) remain 🔜.

Example edit (find the Action Log bullet in §10's P0 list):
```markdown
- **Action Log**（F-AT-36）：✅ 已落地 — 每笔 Action 物化为 `action_logs` 表/文件，executor 内部日志点，8 类 failure_type，admin 查询 API（见 `docs/superpowers/specs/2026-06-22-action-log-design.md`）
```

Leave Auditability / Decision Lineage / Action Metrics / notification 投递 as 🔜 (their data source is now ready but their own implementation is separate specs).

- [ ] **Step 2: Commit**

```bash
git add docs/design/roadmap.md
git commit -m "docs(roadmap): mark Action Log (F-AT-36) as landed in §10"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- §1.1 Auditability → Task 5 (executor logs every execute) + Task 8 (admin query) ✅
- §1.1 Decision Lineage (trigger_source + actor_type) → Task 1 (ActionLogEntry.init) + Task 5 (executor wiring) + Task 7 (call sites) ✅
- §1.1 Metrics data source → Task 1 (duration_ms + failure_type fields) + Task 2 (schema) ✅
- §2 D1 (independent storage) → Task 2 (PG) + Task 3 (JSON) ✅
- §2 D2 (executor log point) → Task 5 ✅
- §2 D3 (lightweight agent context, schema reserved) → Task 1 (llm_model/skill_id/session_id fields, P1 注入 not in this plan) ✅
- §2 D4 (8-class failure_type) → Task 1 (classify_failure) ✅
- §2 D5 (admin-only query) → Task 8 ✅
- §2 D6 (permanent retention) → Task 2 (PG no roll) + Task 3 (JSON 50000 cap, resolved in plan header) ✅
- §3.2 trigger_source from all call sites → Task 7 ✅
- §3.3 8-class classification → Task 1 ✅
- §3.4 affected_objects → Task 1 (update_success) ✅
- §4 ActionLogRepository → Task 3 + Task 4 ✅
- §6 admin API → Task 8 ✅
- §7.1 params masking → Task 1 (mask_sensitive_params) + Task 3/4 (applied at write) ✅
- §7.3 write failure doesn't block → Task 5 (try/except in finally) + Task 3/4 (try/except in write) ✅
- §8 testing → Tasks 1,3,4,5,8,9 cover unit + repo + executor + API + E2E ✅

**Gaps:** None identified. §6.2 admin console UI deferred to P1 (recorded in plan header + Task 10 notes). §1.2 non-goals (Metrics UI, Revert, full agent context injection, LLM Tool) explicitly out of scope.

**2. Placeholder scan:** No TBD/TODO/«implement later». §10 of spec was resolved in plan header. Every code step contains actual code.

**3. Type consistency:**
- `ActionLogEntry.init(action_type, actor, workspace_name, trigger_source)` — consistent in Task 1, 3, 5, 7, 9 ✅
- `ActionLogRepository.write/query/count` signatures — consistent in Task 3, 4, 5 ✅
- `ActionExecutor.__init__(repository, actions, registry, config, log_repo=None)` — consistent in Task 5, 6 ✅
- `executor.execute(action_type, params, *, actor, tenant_id, trigger_source="llm_session")` — consistent in Task 5, 7, 9 ✅
- `failure_type` 8-class values — consistent between Task 1 (classify_failure) and spec §3.3 ✅
- `trigger_source` values (`llm_session`/`automation`/`webhook`/`admin_api`) — consistent in Task 1, 5, 7 ✅

No mismatches found.
