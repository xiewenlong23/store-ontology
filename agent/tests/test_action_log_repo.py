"""ActionLogRepository 测试：JSON 后端（必跑）+ PG 后端（PG 不可用时 skip）。

从 agent/ 跑：.venv/bin/pytest tests/test_action_log_repo.py -v
"""
import pytest

from engine.action_log import ActionLogEntry
from engine.action_log_repo import (
    JSONFileActionLogRepository,
    PgActionLogRepository,
    build_action_log_repo,
)


# ============ 辅助 ============

def _entry(action_type="a", outcome="success", actor_id="u1", ts=None, **kw):
    e = ActionLogEntry.init(action_type, {"user_id": actor_id, "role": "r"},
                            "ws", "llm_session")
    e.outcome = outcome
    e.timestamp = ts or "2026-06-22T10:00:00"
    for k, v in kw.items():
        setattr(e, k, v)
    return e


# ============ JSON 后端（必跑）============

def test_json_write_then_query_roundtrip(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("a1", "success", "u1"))
    rows = repo.query("ws")
    assert len(rows) == 1
    assert rows[0].action_type == "a1"
    assert rows[0].outcome == "success"


def test_json_query_filters_by_action_type_and_outcome(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("a1", "success", "u1"))
    repo.write(_entry("a2", "failure", "u2", failure_type="invalid_param"))
    assert len(repo.query("ws", action_type="a1")) == 1
    assert len(repo.query("ws", outcome="failure")) == 1
    assert len(repo.query("ws", failure_type="invalid_param")) == 1


def test_json_query_pagination(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    for i in range(5):
        repo.write(_entry(f"a{i}", "success", "u1"))
    assert len(repo.query("ws", limit=2)) == 2
    assert len(repo.query("ws", limit=2, offset=4)) == 1


def test_json_count(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("a1", "success", "u1"))
    repo.write(_entry("a2", "failure", "u2"))
    assert repo.count("ws") == 2
    assert repo.count("ws", outcome="success") == 1


def test_json_rolling_cap(tmp_path):
    """超过 cap 截断到 cap（spec §10.1 决议 50000，测试用小 cap）。"""
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo._cap = 3
    for i in range(4):
        repo.write(_entry("a", "success", "u1"))
    assert repo.count("ws") == 3  # 截断到 cap


def test_json_write_masks_sensitive_params(tmp_path):
    """写入时敏感字段掩码（spec §7.1）。"""
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    e = _entry("a", "success", "u1")
    e.params = {"username": "admin", "password": "s3cr3t"}
    repo.write(e)
    rows = repo.query("ws")
    assert rows[0].params == {"username": "admin", "password": "***"}


def test_build_action_log_repo_json_when_no_pg(tmp_path, monkeypatch):
    """无 PG 时工厂返回 JSON 实现（conftest 已删 DATABASE_URL 保证无 PG）。"""
    monkeypatch.setattr("engine.action_log_repo.is_pg_enabled", lambda: False)
    repo = build_action_log_repo(workspace_name="ws", data_dir=str(tmp_path))
    assert repo.storage_kind == "json"


# ============ PG 后端（PG 不可用时 skip）============

def _pg_available():
    from engine.db import is_pg_enabled, ping
    return is_pg_enabled() and ping()


@pytest.fixture
def pg_repo(monkeypatch):
    """配置 PG + migrate + 可用性检查；不可用则 skip。

    conftest 的 autouse fixture 先删 DATABASE_URL；本 fixture 后 setenv 覆盖。
    """
    from engine import db
    # 用 .env 的 DATABASE_URL（若存在）或测试库
    import os
    dburl = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not dburl:
        pytest.skip("无 TEST_DATABASE_URL/DATABASE_URL，跳过 PG repo 测试")
    monkeypatch.setenv("DATABASE_URL", dburl)
    db._reset_pg_state()
    if not (db.is_pg_enabled() and db.ping()):
        pytest.skip("PG 不可用")
    db.migrate()  # 建 action_logs 表（幂等）
    db.execute("DELETE FROM action_logs WHERE workspace_name = %s", ("ws_pg",))
    yield PgActionLogRepository("ws_pg")
    db.execute("DELETE FROM action_logs WHERE workspace_name = %s", ("ws_pg",))


def test_pg_write_then_query(pg_repo):
    pg_repo.write(_entry("a1", "success", "u1"))
    rows = pg_repo.query("ws_pg")
    assert len(rows) == 1
    assert rows[0].action_type == "a1"


def test_pg_query_filters_and_pagination(pg_repo):
    pg_repo.write(_entry("a1", "success", "u1"))
    pg_repo.write(_entry("a2", "failure", "u2", failure_type="invalid_param"))
    assert len(pg_repo.query("ws_pg", outcome="success")) == 1
    assert len(pg_repo.query("ws_pg", limit=1)) == 1


def test_pg_count(pg_repo):
    pg_repo.write(_entry("a1", "success", "u1"))
    pg_repo.write(_entry("a2", "failure", "u2"))
    assert pg_repo.count("ws_pg") == 2


def test_build_action_log_repo_pg_when_available(pg_repo, monkeypatch):
    """PG 可用时工厂返回 PG 实现。"""
    repo = build_action_log_repo("ws_pg")
    assert repo.storage_kind == "pg"
