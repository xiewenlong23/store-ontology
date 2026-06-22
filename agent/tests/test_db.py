"""WP1 PG 连接层测试。

验证 engine/db.py 的连接池 + migrate + execute/query helper。
依赖：docker compose up -d（pgvector/pgvector:pg16 on :5433）。

若 PG 不可用（DATABASE_URL 未配或实例未起），相关测试 skip 而非失败
（保持 CI 在无 PG 环境也能跑）。
"""
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def pg_enabled(monkeypatch):
    """设置 DATABASE_URL 并清缓存，确保 is_pg_enabled 反映测试环境。

    若 PG 实例不可达，pytest.skip 让测试跳过（不失败）。
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql://ontology:ontology@localhost:5433/ontology")
    # 清缓存 + 关旧池
    from engine import db as db_mod
    db_mod._reset_pg_state()
    if not db_mod.ping():
        pytest.skip("PG 实例不可用（需 docker compose up -d）")
    db_mod.migrate()  # 确保表存在
    yield
    db_mod._reset_pg_state()


class TestPgEnabled:

    def test_enabled_when_url_set(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@z/db")
        from engine import db as db_mod
        db_mod._reset_pg_state()
        assert db_mod.is_pg_enabled() is True

    def test_disabled_when_url_missing(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from engine import db as db_mod
        db_mod._reset_pg_state()
        assert db_mod.is_pg_enabled() is False


class TestPGDisabledBehavior:
    """PG 未配置时抛 PGNotConfigured，让上层回落 JSONFileRepository。"""

    def test_transaction_raises_when_disabled(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from engine import db as db_mod
        db_mod._reset_pg_state()
        with pytest.raises(db_mod.PGNotConfigured):
            with db_mod.transaction() as conn:
                pass

    def test_execute_raises_when_disabled(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from engine import db as db_mod
        db_mod._reset_pg_state()
        with pytest.raises(db_mod.PGNotConfigured):
            db_mod.execute("SELECT 1")

    def test_ping_false_when_disabled(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from engine import db as db_mod
        db_mod._reset_pg_state()
        assert db_mod.ping() is False


class TestPGEnabled:
    """PG 可用时的连接 + CRUD helper（依赖 docker compose up）。"""

    def test_ping_ok(self, pg_enabled):
        from engine import db as db_mod
        assert db_mod.ping() is True

    def test_migrate_creates_all_tables(self, pg_enabled):
        from engine import db as db_mod
        tables = db_mod.query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name")
        names = {t["table_name"] for t in tables}
        # 5 张主表
        assert {"object_types", "object_type_properties", "link_types",
                "action_types", "entities"}.issubset(names)

    def test_pgvector_extension_installed(self, pg_enabled):
        from engine import db as db_mod
        ext = db_mod.query("SELECT extname FROM pg_extension WHERE extname='vector'")
        assert len(ext) == 1
        assert ext[0]["extname"] == "vector"

    def test_execute_and_query_roundtrip(self, pg_enabled):
        from engine import db as db_mod
        # 用 entities 表（schema 已建）测 INSERT/SELECT/DELETE
        db_mod.execute(
            "INSERT INTO entities (workspace_name, object_type, id, org_unit_id, data) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            ("_test_ws", "_TestType", "_test_id_1", "*", '{"name":"test"}'))
        rows = db_mod.query(
            "SELECT id, data FROM entities WHERE workspace_name=%s AND object_type=%s",
            ("_test_ws", "_TestType"))
        assert len(rows) >= 1
        # 清理
        db_mod.execute(
            "DELETE FROM entities WHERE workspace_name=%s AND object_type=%s",
            ("_test_ws", "_TestType"))
        rows_after = db_mod.query(
            "SELECT id FROM entities WHERE workspace_name=%s AND object_type=%s",
            ("_test_ws", "_TestType"))
        assert rows_after == []

    def test_transaction_rollback_on_exception(self, pg_enabled):
        from engine import db as db_mod
        # 插一条 + 抛异常 → rollback，数据不应存在
        try:
            with db_mod.transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO entities (workspace_name, object_type, id, data) "
                        "VALUES (%s, %s, %s, %s)",
                        ("_test_ws_rb", "_TestType", "_rb_id", '{"x":1}'))
                raise ValueError("simulated")
        except ValueError:
            pass
        rows = db_mod.query(
            "SELECT id FROM entities WHERE workspace_name=%s AND id=%s",
            ("_test_ws_rb", "_rb_id"))
        assert rows == [], "事务回滚后数据不应存在"

    def test_query_one_returns_none_when_empty(self, pg_enabled):
        from engine import db as db_mod
        result = db_mod.query_one(
            "SELECT id FROM entities WHERE workspace_name=%s AND id=%s",
            ("_nonexistent_ws", "_nonexistent_id"))
        assert result is None
