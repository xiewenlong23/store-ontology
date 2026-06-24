# Action Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggregate the landed `action_logs` into operational metrics (success rate / failure classification / P95 latency) exposed via an admin-only API, closing the agent-observability half of the P0 governance loop.

**Architecture:** Pure read path — no new storage, no new tables, no executor changes. A new `aggregate()` method on `ActionLogRepository` (PG via SQL `percentile_cont` + `FILTER`; JSON via in-memory `Counter` + sorted-percentile) computes metrics on demand from the existing `action_logs`. One new admin GET endpoint returns the aggregated JSON. Reuses `require_admin` + `bootstrap_workspace.log_repo` established by Action Log.

**Tech Stack:** Python 3 (`agent/engine/`), PostgreSQL via psycopg3 (`percentile_cont`), JSON file backend, FastAPI, pytest.

**Spec:** [`docs/superpowers/specs/2026-06-24-action-metrics-design.md`](../specs/2026-06-24-action-metrics-design.md)

**Open questions from spec §8 — RESOLVED in this plan:**
1. Default 30-day window — kept (aligns with Palantir; `since` overrides).
2. per-trigger_source dimension — NOT added (M4 holds; trigger_source remains a filter, not a grouping dimension).
3. P95 only — kept (YAGNI; P50/P99 deferred to when a dashboard asks for them).

**Branch:** `feat/action-metrics` (already created from `main`).

---

## File Structure

**Create:**
- `agent/routers/action_metrics.py` — admin GET endpoint
- `agent/tests/test_action_metrics_repo.py` — aggregate() unit tests (JSON required, PG skip-if-unavailable)
- `agent/tests/test_action_metrics_api.py` — admin API tests

**Modify:**
- `agent/engine/action_log_repo.py` — add `aggregate()` to abstract + `JSONFileActionLogRepository` + `PgActionLogRepository`
- `agent/routers/__init__.py` — export `action_metrics_router`
- `agent/main.py` — include `action_metrics_router`
- `docs/design/roadmap.md` — mark Action Metrics ✅ in §10

**Do NOT touch:** executor.py, schema.sql, workspace_bootstrap.py, action_log.py (pure read path).

---

### Task 1: `aggregate()` on ActionLogRepository — JSON backend

**Files:**
- Modify: `agent/engine/action_log_repo.py` (add to abstract + JSONFileActionLogRepository)
- Test: `agent/tests/test_action_metrics_repo.py`

- [ ] **Step 1: Write the failing test for JSON aggregate**

`agent/tests/test_action_metrics_repo.py`:
```python
"""ActionLogRepository.aggregate() 测试：JSON 后端必跑，PG 后端 skip-if-unavailable。

从 agent/ 跑：.venv/bin/pytest tests/test_action_metrics_repo.py -v
"""
import math

import pytest

from engine.action_log import ActionLogEntry
from engine.action_log_repo import JSONFileActionLogRepository


def _entry(action_type="a", outcome="success", duration_ms=None,
           failure_type=None, ts="2026-06-20T10:00:00"):
    e = ActionLogEntry.init(action_type, {"user_id": "u1", "role": "r"},
                            "ws", "llm_session")
    e.outcome = outcome
    e.timestamp = ts
    e.duration_ms = duration_ms
    e.failure_type = failure_type
    return e


def test_aggregate_empty_logs(tmp_path):
    """空 log → total=0，success_rate/p95 为 null，by_failure_type 全 0。"""
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    m = repo.aggregate("ws")
    assert m["overall"]["total"] == 0
    assert m["overall"]["success_rate"] is None
    assert m["overall"]["p95_duration_ms"] is None
    # 8 类 failure_type 全 0
    assert sum(m["by_failure_type"].values()) == 0
    assert set(m["by_failure_type"].keys()) == {
        "unknown_action", "invalid_param", "permission_denied", "submission_failed",
        "entity_not_found", "illegal_transition", "side_effect_error", "unclassified"}
    assert m["by_action_type"] == {}


def test_aggregate_overall_counts(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("a", "success", duration_ms=10))
    repo.write(_entry("a", "success", duration_ms=20))
    repo.write(_entry("a", "failure", duration_ms=5, failure_type="invalid_param"))
    m = repo.aggregate("ws")
    assert m["overall"]["total"] == 3
    assert m["overall"]["success"] == 2
    assert m["overall"]["failure"] == 1
    assert m["overall"]["success_rate"] == round(2 / 3, 3)


def test_aggregate_p95_calculation(tmp_path):
    """5 条 duration [10,20,30,40,100]，P95 idx=ceil(0.95*5)=5 → 100。"""
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    for d in (10, 20, 30, 40, 100):
        repo.write(_entry("a", "success", duration_ms=d))
    m = repo.aggregate("ws")
    assert m["overall"]["p95_duration_ms"] == 100


def test_aggregate_by_action_type(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("create_clearance_task", "success", duration_ms=100))
    repo.write(_entry("create_clearance_task", "failure", duration_ms=5,
                     failure_type="invalid_param"))
    repo.write(_entry("deduct_stock", "success", duration_ms=15))
    m = repo.aggregate("ws")
    assert set(m["by_action_type"].keys()) == {"create_clearance_task", "deduct_stock"}
    cct = m["by_action_type"]["create_clearance_task"]
    assert cct["total"] == 2 and cct["success"] == 1 and cct["failure"] == 1
    assert cct["success_rate"] == 0.5


def test_aggregate_by_failure_type_counts_all_8_classes(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    for ft in ("invalid_param", "invalid_param", "permission_denied", "entity_not_found"):
        repo.write(_entry("a", "failure", duration_ms=5, failure_type=ft))
    m = repo.aggregate("ws")
    assert m["by_failure_type"]["invalid_param"] == 2
    assert m["by_failure_type"]["permission_denied"] == 1
    assert m["by_failure_type"]["entity_not_found"] == 1
    # 未出现的类为 0
    assert m["by_failure_type"]["side_effect_error"] == 0
    assert m["by_failure_type"]["unclassified"] == 0


def test_aggregate_window_filter(tmp_path):
    """since/until 过滤生效：窗口外的 log 不计入。"""
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("a", "success", duration_ms=10, ts="2026-06-01T00:00:00"))
    repo.write(_entry("a", "success", duration_ms=20, ts="2026-06-15T00:00:00"))
    m = repo.aggregate("ws", since="2026-06-10T00:00:00", until="2026-06-20T00:00:00")
    assert m["overall"]["total"] == 1  # 只有 06-15 那条在窗内


def test_aggregate_action_type_filter(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("a", "success", duration_ms=10))
    repo.write(_entry("b", "success", duration_ms=20))
    m = repo.aggregate("ws", action_type="a")
    # overall 仍只算 a
    assert m["overall"]["total"] == 1
    assert list(m["by_action_type"].keys()) == ["a"]


def test_aggregate_window_in_response(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    m = repo.aggregate("ws", since="2026-06-01T00:00:00", until="2026-06-30T00:00:00")
    assert m["window"]["since"] == "2026-06-01T00:00:00"
    assert m["window"]["until"] == "2026-06-30T00:00:00"
```

Run: `cd agent && .venv/bin/pytest tests/test_action_metrics_repo.py -v`
Expected: FAIL — `JSONFileActionLogRepository` has no `aggregate` attribute.

- [ ] **Step 2: Add `aggregate()` to the abstract class**

In `agent/engine/action_log_repo.py`, add to the `ActionLogRepository` abstract class (after the `count` method):

```python
    def aggregate(self, ws_name: str, *, since: Optional[str] = None,
                  until: Optional[str] = None, action_type: Optional[str] = None,
                  trigger_source: Optional[str] = None) -> dict:
        """聚合 action_logs 产出 Metrics（spec §3.2 结构）。

        返回 {window, filters, overall, by_action_type, by_failure_type}。
        子类实现具体聚合（PG SQL / JSON 内存）。
        """
        raise NotImplementedError
```

- [ ] **Step 3: Implement JSON `aggregate()` + shared helpers**

Add a module-level helper for the response skeleton, and implement on `JSONFileActionLogRepository`. Place the helper near the other module-level helpers (`_entry_to_dict` etc.):

```python
# 8 类 failure_type（spec §3.3，对齐 Action Log classify_failure）
_FAILURE_TYPES = (
    "unknown_action", "invalid_param", "permission_denied", "submission_failed",
    "entity_not_found", "illegal_transition", "side_effect_error", "unclassified",
)


def _p95(values: list) -> Optional[int]:
    """P95：排序后取 idx = ceil(0.95 * n) - 1。空 → None。"""
    vs = sorted(v for v in values if v is not None)
    if not vs:
        return None
    idx = math.ceil(0.95 * len(vs)) - 1
    idx = max(0, min(idx, len(vs) - 1))
    return vs[idx]


def _bucket(total, success, failure, durations):
    """单维度的聚合桶。"""
    return {
        "total": total,
        "success": success,
        "failure": failure,
        "success_rate": round(success / total, 3) if total else None,
        "p95_duration_ms": _p95(durations),
    }
```

(Add `import math` at the top of the file with the other imports.)

Then add the method to `JSONFileActionLogRepository`:

```python
    def aggregate(self, ws_name: str, *, since=None, until=None,
                  action_type=None, trigger_source=None) -> dict:
        rows = self._load()
        # 过滤
        out = []
        for r in rows:
            if r.get("workspace_name") != ws_name:
                continue
            ts = r.get("timestamp", "")
            if since and ts < since:
                continue
            if until and ts > until:
                continue
            if action_type and r.get("action_type") != action_type:
                continue
            if trigger_source and r.get("trigger_source") != trigger_source:
                continue
            out.append(r)

        # overall
        total = len(out)
        succ = sum(1 for r in out if r.get("outcome") == "success")
        fail = sum(1 for r in out if r.get("outcome") == "failure")
        overall = _bucket(total, succ, fail, [r.get("duration_ms") for r in out])

        # by_action_type
        by_action = {}
        for r in out:
            at = r.get("action_type")
            if not at:
                continue
            b = by_action.setdefault(at, {"total": 0, "success": 0, "failure": 0,
                                          "durations": []})
            b["total"] += 1
            if r.get("outcome") == "success":
                b["success"] += 1
            elif r.get("outcome") == "failure":
                b["failure"] += 1
            if r.get("duration_ms") is not None:
                b["durations"].append(r["duration_ms"])
        by_action_final = {at: _bucket(b["total"], b["success"], b["failure"],
                                       b["durations"])
                           for at, b in by_action.items()}

        # by_failure_type（仅 failure 行，全 8 类补 0）
        from collections import Counter
        ft_counter = Counter(r.get("failure_type") for r in out
                             if r.get("outcome") == "failure" and r.get("failure_type"))
        by_failure = {ft: ft_counter.get(ft, 0) for ft in _FAILURE_TYPES}

        return {
            "window": {"since": since, "until": until},
            "filters": {"action_type": action_type, "trigger_source": trigger_source},
            "overall": overall,
            "by_action_type": by_action_final,
            "by_failure_type": by_failure,
        }
```

- [ ] **Step 4: Run the JSON aggregate tests**

Run: `cd agent && .venv/bin/pytest tests/test_action_metrics_repo.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add agent/engine/action_log_repo.py agent/tests/test_action_metrics_repo.py
git commit -m "feat(action-metrics): JSONFileActionLogRepository.aggregate() + 8 unit tests"
```

---

### Task 2: `aggregate()` PG backend

**Files:**
- Modify: `agent/engine/action_log_repo.py` (PgActionLogRepository)
- Test: `agent/tests/test_action_metrics_repo.py` (add PG tests, skip-if-unavailable)

- [ ] **Step 1: Add the failing PG aggregate test**

Append to `agent/tests/test_action_metrics_repo.py`:

```python
# ============ PG 后端（PG 不可用时 skip）============

def _pg_available():
    from engine.db import is_pg_enabled, ping
    return is_pg_enabled() and ping()


@pytest.fixture
def pg_repo(monkeypatch):
    from engine import db
    import os
    dburl = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not dburl:
        pytest.skip("无 TEST_DATABASE_URL/DATABASE_URL，跳过 PG metrics 测试")
    monkeypatch.setenv("DATABASE_URL", dburl)
    db._reset_pg_state()
    if not (db.is_pg_enabled() and db.ping()):
        pytest.skip("PG 不可用")
    db.migrate()
    db.execute("DELETE FROM action_logs WHERE workspace_name = %s", ("ws_pg",))
    from engine.action_log_repo import PgActionLogRepository
    yield PgActionLogRepository("ws_pg")
    db.execute("DELETE FROM action_logs WHERE workspace_name = %s", ("ws_pg",))


def _pg_entry(repo, action_type, outcome, duration_ms=None, failure_type=None):
    from engine.action_log import ActionLogEntry
    e = ActionLogEntry.init(action_type, {"user_id": "u1", "role": "r"},
                            "ws_pg", "llm_session")
    e.outcome = outcome
    e.duration_ms = duration_ms
    e.failure_type = failure_type
    repo.write(e)


def test_pg_aggregate_overall(pg_repo):
    _pg_entry(pg_repo, "a", "success", duration_ms=10)
    _pg_entry(pg_repo, "a", "success", duration_ms=20)
    _pg_entry(pg_repo, "a", "failure", duration_ms=5, failure_type="invalid_param")
    m = pg_repo.aggregate("ws_pg")
    assert m["overall"]["total"] == 3
    assert m["overall"]["success"] == 2
    assert m["overall"]["failure"] == 1


def test_pg_aggregate_p95(pg_repo):
    for d in (10, 20, 30, 40, 100):
        _pg_entry(pg_repo, "a", "success", duration_ms=d)
    m = pg_repo.aggregate("ws_pg")
    assert m["overall"]["p95_duration_ms"] == 100


def test_pg_aggregate_by_action_type(pg_repo):
    _pg_entry(pg_repo, "create", "success", duration_ms=100)
    _pg_entry(pg_repo, "create", "failure", duration_ms=5, failure_type="invalid_param")
    _pg_entry(pg_repo, "deduct", "success", duration_ms=15)
    m = pg_repo.aggregate("ws_pg")
    assert set(m["by_action_type"].keys()) == {"create", "deduct"}
    assert m["by_action_type"]["create"]["total"] == 2


def test_pg_aggregate_window_filter(pg_repo):
    _pg_entry(pg_repo, "a", "success", duration_ms=10)
    # 直接改 timestamp 模拟老数据
    from engine.db import execute
    execute("UPDATE action_logs SET timestamp='2026-05-01' WHERE workspace_name='ws_pg'",
            ())
    m = pg_repo.aggregate("ws_pg", since="2026-06-01")
    assert m["overall"]["total"] == 0
```

Run: `cd agent && .venv/bin/pytest tests/test_action_metrics_repo.py -k pg -v`
Expected: 4 SKIPPED (no local PG)

- [ ] **Step 2: Implement PG `aggregate()`**

Add the method to `PgActionLogRepository` in `agent/engine/action_log_repo.py`:

```python
    def aggregate(self, ws_name: str, *, since=None, until=None,
                  action_type=None, trigger_source=None) -> dict:
        from engine.db import query as db_query, query_one
        # 公共 WHERE 子句 + 参数
        clauses = ["workspace_name = %s"]
        params: list = [ws_name]
        if since:
            clauses.append("timestamp >= %s"); params.append(since)
        if until:
            clauses.append("timestamp <= %s"); params.append(until)
        if action_type:
            clauses.append("action_type = %s"); params.append(action_type)
        if trigger_source:
            clauses.append("trigger_source = %s"); params.append(trigger_source)
        where = " AND ".join(clauses)
        base_params = tuple(params)

        # overall（单行）
        overall_row = query_one(f"""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE outcome='success') AS success,
                   COUNT(*) FILTER (WHERE outcome='failure') AS failure,
                   COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms), 0)::int AS p95
            FROM action_logs WHERE {where}
        """, base_params) or {}
        total = int(overall_row.get("total") or 0)
        succ = int(overall_row.get("success") or 0)
        fail = int(overall_row.get("failure") or 0)
        # PG percentile_cont 对空集返回 NULL；0 行时 p95 置 None
        p95 = int(overall_row["p95"]) if total and overall_row.get("p95") else None
        overall = {
            "total": total, "success": succ, "failure": fail,
            "success_rate": round(succ / total, 3) if total else None,
            "p95_duration_ms": p95,
        }

        # by_action_type
        by_action_rows = db_query(f"""
            SELECT action_type,
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE outcome='success') AS success,
                   COUNT(*) FILTER (WHERE outcome='failure') AS failure,
                   COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms), 0)::int AS p95
            FROM action_logs WHERE {where}
            GROUP BY action_type
        """, base_params)
        by_action = {}
        for r in by_action_rows:
            t = int(r["total"]); s = int(r["success"]); f = int(r["failure"])
            by_action[r["action_type"]] = {
                "total": t, "success": s, "failure": f,
                "success_rate": round(s / t, 3) if t else None,
                "p95_duration_ms": int(r["p95"]) if t and r.get("p95") else None,
            }

        # by_failure_type（8 类补 0）
        ft_rows = db_query(f"""
            SELECT COALESCE(failure_type, '') AS ft, COUNT(*) AS n
            FROM action_logs
            WHERE {where} AND outcome='failure'
            GROUP BY failure_type
        """, base_params)
        ft_map = {r["ft"]: int(r["n"]) for r in ft_rows if r["ft"]}
        by_failure = {ft: ft_map.get(ft, 0) for ft in _FAILURE_TYPES}

        return {
            "window": {"since": since, "until": until},
            "filters": {"action_type": action_type, "trigger_source": trigger_source},
            "overall": overall,
            "by_action_type": by_action,
            "by_failure_type": by_failure,
        }
```

- [ ] **Step 3: Run the full repo test file**

Run: `cd agent && .venv/bin/pytest tests/test_action_metrics_repo.py -v`
Expected: 8 JSON tests PASS + 4 PG tests SKIP (or PASS if local PG available)

- [ ] **Step 4: Commit**

```bash
git add agent/engine/action_log_repo.py agent/tests/test_action_metrics_repo.py
git commit -m "feat(action-metrics): PgActionLogRepository.aggregate() + 4 PG tests (skip-if-unavailable)"
```

---

### Task 3: Admin API endpoint

**Files:**
- Create: `agent/routers/action_metrics.py`
- Modify: `agent/routers/__init__.py`
- Modify: `agent/main.py`
- Test: `agent/tests/test_action_metrics_api.py`

- [ ] **Step 1: Write the failing API test**

`agent/tests/test_action_metrics_api.py`:
```python
"""admin action-metrics API 测试（spec §3.1/§3.2）：鉴权/空响应/有数据/过滤。

JWT_SECRET 由 conftest 设；AUTH_REQUIRED 由 conftest 设 false。
"""
import pytest
from fastapi.testclient import TestClient

from engine.action_log import ActionLogEntry


class FakeRepo:
    """复用 aggregate 返回值，不依赖真实存储。"""
    storage_kind = "fake"
    def __init__(self, agg_result):
        self._agg = agg_result
    def aggregate(self, ws, **kw):
        return self._agg


EMPTY_AGG = {
    "window": {"since": None, "until": None},
    "filters": {"action_type": None, "trigger_source": None},
    "overall": {"total": 0, "success": 0, "failure": 0,
                "success_rate": None, "p95_duration_ms": None},
    "by_action_type": {},
    "by_failure_type": {ft: 0 for ft in (
        "unknown_action", "invalid_param", "permission_denied", "submission_failed",
        "entity_not_found", "illegal_transition", "side_effect_error", "unclassified")},
}


@pytest.fixture
def client(monkeypatch):
    """放行 require_admin（patch router 模块别名，与 test_action_logs_api 一致）。"""
    monkeypatch.setattr("agent.routers.action_metrics.require_admin",
                        lambda ws, **kw: None)
    from agent.main import app
    return TestClient(app)


def test_metrics_empty(client, monkeypatch):
    monkeypatch.setattr("agent.routers.action_metrics._get_log_repo",
                        lambda ws: FakeRepo(EMPTY_AGG))
    r = client.get("/api/admin/customers/jjy/action-metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"]["total"] == 0
    assert body["overall"]["success_rate"] is None
    assert len(body["by_failure_type"]) == 8


def test_metrics_with_data(client, monkeypatch):
    agg = dict(EMPTY_AGG)
    agg["overall"] = {"total": 3, "success": 2, "failure": 1,
                      "success_rate": 0.667, "p95_duration_ms": 100}
    agg["by_action_type"] = {"create_clearance_task": {
        "total": 3, "success": 2, "failure": 1, "success_rate": 0.667,
        "p95_duration_ms": 100}}
    monkeypatch.setattr("agent.routers.action_metrics._get_log_repo",
                        lambda ws: FakeRepo(agg))
    r = client.get("/api/admin/customers/jjy/action-metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"]["total"] == 3
    assert "create_clearance_task" in body["by_action_type"]


def test_metrics_passes_query_params(client, monkeypatch):
    """since/until/action_type/trigger_source 透传到 aggregate。"""
    captured = {}
    class CaptureRepo:
        storage_kind = "fake"
        def aggregate(self, ws, **kw):
            captured.update(kw)
            return EMPTY_AGG
    monkeypatch.setattr("agent.routers.action_metrics._get_log_repo",
                        lambda ws: CaptureRepo())
    r = client.get("/api/admin/customers/jjy/action-metrics"
                   "?since=2026-06-01&until=2026-06-30&action_type=create&trigger_source=automation")
    assert r.status_code == 200
    assert captured["since"] == "2026-06-01"
    assert captured["until"] == "2026-06-30"
    assert captured["action_type"] == "create"
    assert captured["trigger_source"] == "automation"


def test_metrics_non_admin_denied(monkeypatch):
    """require_admin 返回 403 时路由转发（patch router 模块别名）。"""
    from fastapi.responses import JSONResponse
    monkeypatch.setattr("agent.routers.action_metrics.require_admin",
                        lambda ws, **kw: JSONResponse(status_code=403,
                                                      content={"detail": "forbidden"}))
    monkeypatch.setattr("agent.routers.action_metrics._get_log_repo",
                        lambda ws: FakeRepo(EMPTY_AGG))
    from agent.main import app
    c = TestClient(app)
    r = c.get("/api/admin/customers/jjy/action-metrics")
    assert r.status_code == 403


def test_metrics_default_window_30_days(client, monkeypatch):
    """不传 since 时默认 30 天前（spec M2）。"""
    captured = {}
    class CaptureRepo:
        storage_kind = "fake"
        def aggregate(self, ws, **kw):
            captured.update(kw)
            return EMPTY_AGG
    monkeypatch.setattr("agent.routers.action_metrics._get_log_repo",
                        lambda ws: CaptureRepo())
    r = client.get("/api/admin/customers/jjy/action-metrics")
    assert r.status_code == 200
    assert captured["since"] is not None  # 默认填了 30 天前
    # until 默认 now
    assert captured["until"] is not None
```

Run: `cd agent && .venv/bin/pytest tests/test_action_metrics_api.py -v`
Expected: FAIL — module `agent.routers.action_metrics` not found.

- [ ] **Step 2: Implement the router**

`agent/routers/action_metrics.py`:
```python
"""admin Action Metrics 查询 API（spec §3.1）。

仅 admin 可访问；从 action_logs 聚合（无物化表，spec M1 按需现算）。
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
```

- [ ] **Step 3: Register the router**

In `agent/routers/__init__.py`, add the import and `__all__` entry:

```python
from agent.routers.action_metrics import router as action_metrics_router
```

Append `"action_metrics_router"` to the `__all__` list.

In `agent/main.py`, update the routers import and include:

```python
from agent.routers import (
    auth_router, admin_router, dashboard_router, webhooks_router,
    action_logs_router, action_metrics_router,
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(dashboard_router)
app.include_router(webhooks_router)
app.include_router(action_logs_router)
app.include_router(action_metrics_router)
```

- [ ] **Step 4: Run the API tests**

Run: `cd agent && .venv/bin/pytest tests/test_action_metrics_api.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add agent/routers/action_metrics.py agent/routers/__init__.py agent/main.py agent/tests/test_action_metrics_api.py
git commit -m "feat(action-metrics): admin GET /action-metrics endpoint + 5 API tests"
```

---

### Task 4: Regression + documentation

**Files:**
- Test: run full suite
- Modify: `docs/design/roadmap.md`

- [ ] **Step 1: Run the full test suite to confirm no regression**

Run: `cd agent && .venv/bin/pytest 2>&1 | tail -3`
Expected: All previously-passing tests still pass; new metrics tests pass. (Action Log had 451 passed; this should be 451 + 8 + 4 + 5 = 468 passed, with the 4 PG metrics tests skipped without local PG.)

- [ ] **Step 2: Mark Action Metrics landed in roadmap §10**

In `docs/design/roadmap.md`, §10's P0 list currently has:

```markdown
- **Action Metrics**（F-AT-40/41）：从 Action Log 聚合，成功率 / 失败分类 / P95 时延，per-action-type + per-workspace。agent 运维可观测性核心。
```

Change to:

```markdown
- **Action Metrics**（F-AT-40/41）：✅ 已落地（feat/action-metrics 分支）— 从 action_logs 按需聚合（无物化表），overall + per-action_type + per-failure_type 8 类计数 + P95 时延，admin API `GET /action-metrics`（默认 30 天窗）。见 [spec](superpowers/specs/2026-06-24-action-metrics-design.md)。
```

- [ ] **Step 3: Commit**

```bash
git add docs/design/roadmap.md
git commit -m "docs(roadmap): mark Action Metrics (F-AT-40/41) as landed in §10"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- §1.1 成功率与时延 → Task 1/2 `_bucket` (total/success/failure/success_rate/p95) + Task 3 endpoint ✅
- §1.1 失败分类计数 → Task 1/2 `by_failure_type` 全 8 类补 0 ✅
- §2 M1 按需现算 → Task 1/2 aggregate() 无物化 ✅
- §2 M2 默认 30 天 → Task 3 endpoint 默认 since/until ✅ (test_metrics_default_window_30_days)
- §2 M3 P95 双后端 → Task 1 JSON `_p95` + Task 2 PG `percentile_cont` ✅
- §2 M4 维度 overall + by_action_type + by_failure_type → Task 1/2 三段返回 ✅
- §2 M5 仅 admin API → Task 3 require_admin ✅ (test_metrics_non_admin_denied)
- §2 M6 复用 8 类 → Task 1 `_FAILURE_TYPES` 常量 ✅
- §3.1 端点 + query params → Task 3 ✅ (test_metrics_passes_query_params)
- §3.2 响应结构 → Task 1/2 返回 dict 形状 + Task 3 透传 ✅
- §3.2 空值约定（total=0 → success_rate/p95 None）→ Task 1 `_bucket` + test_aggregate_empty_logs ✅
- §4.1 aggregate() 抽象 + 双实现 → Task 1/2 ✅
- §5 改造点（repo + router + __init__ + main）→ Task 1/2/3 ✅
- §6 测试策略 → Task 1/2/3 + Task 4 回归 ✅

**Gaps:** None. §1.2 non-goals (dashboard UI / 告警 / 物化 / per-actor / LLM Tool) explicitly out of scope.

**2. Placeholder scan:** No TBD/TODO/«implement later». §8 resolved in plan header. Every code step contains actual code.

**3. Type consistency:**
- `aggregate(ws_name, *, since, until, action_type, trigger_source) -> dict` — consistent Task 1/2/3 ✅
- Response shape `{window, filters, overall, by_action_type, by_failure_type}` — consistent across abstract docstring, JSON impl, PG impl, API test `EMPTY_AGG` ✅
- `_FAILURE_TYPES` 8-tuple — consistent between Task 1 module constant and test expectation ✅
- `_bucket(total, success, failure, durations)` helper — used identically in JSON overall + by_action_type ✅
- `require_admin(ws)` returns None/JSONResponse pattern — consistent with action_logs.py ✅

No mismatches found.
