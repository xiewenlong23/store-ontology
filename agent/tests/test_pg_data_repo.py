"""WP4 PgDataRepository 测试。

验证 read/read_one/write/delete + TenantContext 过滤 + workspace 隔离 +
edits-only 拒绝。依赖 docker compose up -d。
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def pg_data_repo(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://ontology:ontology@localhost:5433/ontology")
    from engine import db as db_mod
    db_mod._reset_pg_state()
    if not db_mod.ping():
        pytest.skip("PG 不可用")
    db_mod.migrate()
    # 清理之前的测试数据
    db_mod.execute("DELETE FROM entities WHERE workspace_name = %s", ("_test_data_ws",))
    # mock registry（最小，含 Task + 普通类型）
    from engine.parser import ObjectType, PropertyDef
    class _Reg:
        object_types = {
            "Task": ObjectType(
                id="Task", label="Task", comment="",
                properties=[PropertyDef(name="id", type="string")],
                storage_file="tasks.json", edits_only_via_actions=True),
            "Region": ObjectType(
                id="Region", label="Region", comment="",
                properties=[PropertyDef(name="id", type="string")],
                storage_file="regions.json", edits_only_via_actions=False),
        }
        link_types = {}
        action_types = {}
    from engine.pg_data_repo import PgDataRepository
    repo = PgDataRepository(workspace_name="_test_data_ws", registry=_Reg())
    yield repo
    db_mod.execute("DELETE FROM entities WHERE workspace_name = %s", ("_test_data_ws",))
    db_mod._reset_pg_state()


class TestRead:

    def test_empty_returns_list(self, pg_data_repo):
        from engine.tenant import TenantContext
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        assert pg_data_repo.read("Task", tc) == []

    def test_workspace_isolation(self, pg_data_repo):
        """不同 workspace 隔离。"""
        from engine.tenant import TenantContext
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        pg_data_repo.write("Region", tc, {"id": "r1", "name": "T"}, bypass_action_check=True)
        # 用另一个 ws 名查询（构造不同 repo 实例）
        from engine.parser import EntityRegistry
        other = type(pg_data_repo)(workspace_name="_other_ws",
                                   registry=pg_data_repo.registry)
        tc2 = TenantContext(workspace_name="_other_ws", org_unit_id="*")
        assert other.read("Region", tc2) == []

    def test_headquarters_reads_all(self, pg_data_repo):
        from engine.tenant import TenantContext
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        pg_data_repo.write("Region", tc, {"id": "r1", "name": "T1"}, bypass_action_check=True)
        pg_data_repo.write("Region", tc, {"id": "r2", "name": "T2"}, bypass_action_check=True)
        rows = pg_data_repo.read("Region", tc)
        assert len(rows) == 2

    def test_org_unit_filter_with_visible_units(self, pg_data_repo):
        """visible_units 集合过滤（region 见子树 store_001/store_002）。

        注：write 强制盖 org_unit_id（与 JSONFileRepository 一致），所以要用
        具体的 org_unit_id TenantContext 写，而不是用 '*' 写后修改。
        """
        from engine.tenant import TenantContext
        # 用具体 org_unit_id 写 3 条
        for rid, store in [("r1", "store_001"), ("r2", "store_002"), ("r3", "region_x")]:
            tc = TenantContext(workspace_name="_test_data_ws", org_unit_id=store)
            pg_data_repo.write("Region", tc,
                               {"id": rid, "name": "x"},
                               bypass_action_check=True)
        # region_x 上下文 + visible_units={region_x, store_001, store_002}
        tc_region = TenantContext(workspace_name="_test_data_ws", org_unit_id="region_x")
        visible = {"region_x", "store_001", "store_002"}
        rows = pg_data_repo.read("Region", tc_region, visible_units=visible)
        ids = {r["id"] for r in rows}
        assert ids == {"r1", "r2", "r3"}  # 全见（在 visible_units 内）

    def test_org_unit_filter_limited(self, pg_data_repo):
        """store_001 上下文 + visible_units={store_001} → 只见 r1。"""
        from engine.tenant import TenantContext
        for rid, store in [("r1", "store_001"), ("r2", "store_002")]:
            tc = TenantContext(workspace_name="_test_data_ws", org_unit_id=store)
            pg_data_repo.write("Region", tc,
                               {"id": rid, "name": "x"},
                               bypass_action_check=True)
        tc_store = TenantContext(workspace_name="_test_data_ws", org_unit_id="store_001")
        rows = pg_data_repo.read("Region", tc_store, visible_units={"store_001"})
        ids = {r["id"] for r in rows}
        assert ids == {"r1"}, f"应只见 r1，实际 {ids}"

    def test_shared_record_visible_to_all(self, pg_data_repo):
        """org_unit_id='*' 的共享数据 → 任何上下文可见。

        用 hq tc 写（'*' 是 hq 默认）。
        """
        from engine.tenant import TenantContext
        tc_hq = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        pg_data_repo.write("Region", tc_hq,
                           {"id": "shared", "name": "shared"},
                           bypass_action_check=True)
        # 任何上下文应见
        tc_store = TenantContext(workspace_name="_test_data_ws", org_unit_id="store_001")
        rows = pg_data_repo.read("Region", tc_store, visible_units={"store_001"})
        ids = {r["id"] for r in rows}
        assert "shared" in ids


class TestReadOne:

    def test_found(self, pg_data_repo):
        from engine.tenant import TenantContext
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        pg_data_repo.write("Region", tc, {"id": "x1", "name": "X"}, bypass_action_check=True)
        got = pg_data_repo.read_one("Region", tc, "x1")
        assert got is not None
        assert got["id"] == "x1"

    def test_not_found_returns_none(self, pg_data_repo):
        from engine.tenant import TenantContext
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        assert pg_data_repo.read_one("Region", tc, "nonexistent") is None


class TestWrite:

    def test_create_then_read(self, pg_data_repo):
        from engine.tenant import TenantContext
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        rec = pg_data_repo.write("Region", tc, {"id": "w1", "name": "Written"},
                                 bypass_action_check=True)
        assert rec["id"] == "w1"
        assert rec["workspace_name"] == "_test_data_ws"
        assert rec["org_unit_id"] == "*"
        # 读回
        got = pg_data_repo.read_one("Region", tc, "w1")
        assert got["name"] == "Written"

    def test_upsert_replaces(self, pg_data_repo):
        """同 id 二次 write 应更新而非插入新行。"""
        from engine.tenant import TenantContext
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        pg_data_repo.write("Region", tc, {"id": "up1", "name": "old"},
                           bypass_action_check=True)
        pg_data_repo.write("Region", tc, {"id": "up1", "name": "new"},
                           bypass_action_check=True)
        rows = pg_data_repo.read("Region", tc)
        assert len([r for r in rows if r["id"] == "up1"]) == 1
        assert pg_data_repo.read_one("Region", tc, "up1")["name"] == "new"

    def test_edits_only_rejects_non_bypass(self, pg_data_repo):
        """Task 标记 edits-only → 不 bypass 应拒绝。"""
        from engine.tenant import TenantContext
        from engine.errors import ActionRequiredError
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        with pytest.raises(ActionRequiredError):
            pg_data_repo.write("Task", tc, {"id": "t1"}, bypass_action_check=False)

    def test_edits_only_allows_bypass(self, pg_data_repo):
        from engine.tenant import TenantContext
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        pg_data_repo.write("Task", tc, {"id": "t1", "status": "created"},
                           bypass_action_check=True)
        got = pg_data_repo.read_one("Task", tc, "t1")
        assert got["status"] == "created"


class TestDelete:

    def test_delete_existing(self, pg_data_repo):
        from engine.tenant import TenantContext
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        pg_data_repo.write("Region", tc, {"id": "d1", "name": "x"},
                           bypass_action_check=True)
        assert pg_data_repo.delete("Region", tc, "d1") is True
        assert pg_data_repo.read_one("Region", tc, "d1") is None

    def test_delete_nonexistent_returns_false(self, pg_data_repo):
        from engine.tenant import TenantContext
        tc = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        assert pg_data_repo.delete("Region", tc, "no_such") is False

    def test_delete_respects_org_scope(self, pg_data_repo):
        """删除应遵守 visible_units 过滤（不能跨 org 删）。

        注：用具体 org_unit_id 写入，让 visible_units 过滤生效。
        """
        from engine.tenant import TenantContext
        tc_store2 = TenantContext(workspace_name="_test_data_ws", org_unit_id="store_002")
        pg_data_repo.write("Region", tc_store2,
                           {"id": "cross1", "name": "x"},
                           bypass_action_check=True)
        # store_001 上下文尝试删 store_002 的记录 → 应失败
        tc_store1 = TenantContext(workspace_name="_test_data_ws", org_unit_id="store_001")
        deleted = pg_data_repo.delete("Region", tc_store1, "cross1",
                                      visible_units={"store_001"})
        assert deleted is False
        # 总部仍能读到
        tc_hq = TenantContext(workspace_name="_test_data_ws", org_unit_id="*")
        got = pg_data_repo.read_one("Region", tc_hq, "cross1")
        assert got is not None
