"""WP3 PgOntologyRepository 测试。

验证 CRUD round-trip：upsert 后 load 等价；delete 后查不到。
依赖：docker compose up -d。
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def pg_ready(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://ontology:ontology@localhost:5433/ontology")
    from engine import db as db_mod
    db_mod._reset_pg_state()
    if not db_mod.ping():
        pytest.skip("PG 不可用")
    db_mod.migrate()
    # 清理之前的测试数据（隔离）
    db_mod.execute("DELETE FROM object_types WHERE workspace_name = %s", ("_test_ont_ws",))
    db_mod.execute("DELETE FROM link_types WHERE workspace_name = %s", ("_test_ont_ws",))
    db_mod.execute("DELETE FROM action_types WHERE workspace_name = %s", ("_test_ont_ws",))
    yield
    db_mod.execute("DELETE FROM object_types WHERE workspace_name = %s", ("_test_ont_ws",))
    db_mod.execute("DELETE FROM link_types WHERE workspace_name = %s", ("_test_ont_ws",))
    db_mod.execute("DELETE FROM action_types WHERE workspace_name = %s", ("_test_ont_ws",))
    db_mod._reset_pg_state()


def _mk_obj(name="Foo", read_roles="", props=None):
    from engine.parser import ObjectType, PropertyDef
    return ObjectType(
        id=name, label=f"{name} (zh)", label_zh=f"{name}", comment=f"{name} test",
        properties=props or [PropertyDef(name="id", type="string"),
                             PropertyDef(name="name", type="string")],
        storage_file=f"{name.lower()}s.json", status="active",
        edits_only_via_actions=False,
        read_roles=read_roles, read_except="",
        write_roles="", write_except="",
    )


class TestObjectTypeCRUD:

    def test_upsert_then_load(self, pg_ready):
        from engine import pg_ontology_repo as repo
        from engine.parser import PropertyDef
        ot = _mk_obj("TestObj", read_roles="admin", props=[
            PropertyDef(name="id", type="string"),
            PropertyDef(name="salary", type="float", read_except="clerk"),
            PropertyDef(name="secret", type="string", read_except="*"),
        ])
        repo.upsert_object_type("_test_ont_ws", ot)
        loaded = repo.load_registry("_test_ont_ws")
        assert "TestObj" in loaded.object_types
        got = loaded.object_types["TestObj"]
        assert got.label_zh == "TestObj"
        assert got.read_roles == "admin"
        assert len(got.properties) == 3
        # 属性级权限元数据 round-trip
        salary = next(p for p in got.properties if p.name == "salary")
        assert salary.read_except == "clerk"
        secret = next(p for p in got.properties if p.name == "secret")
        assert secret.read_except == "*"

    def test_upsert_replaces_properties(self, pg_ready):
        """二次 upsert 应全量替换 properties（不是追加）。"""
        from engine import pg_ontology_repo as repo
        from engine.parser import PropertyDef
        ot1 = _mk_obj("ReplaceTest", props=[
            PropertyDef(name="id", type="string"),
            PropertyDef(name="a", type="string"),
            PropertyDef(name="b", type="string"),
        ])
        repo.upsert_object_type("_test_ont_ws", ot1)
        ot2 = _mk_obj("ReplaceTest", props=[
            PropertyDef(name="id", type="string"),
            PropertyDef(name="c", type="int"),   # a/b 没了，换 c
        ])
        repo.upsert_object_type("_test_ont_ws", ot2)
        loaded = repo.load_registry("_test_ont_ws")
        got = loaded.object_types["ReplaceTest"]
        prop_names = {p.name for p in got.properties}
        assert prop_names == {"id", "c"}, f"应替换为 id+c，实际 {prop_names}"

    def test_upsert_same_name_updates_metadata(self, pg_ready):
        from engine import pg_ontology_repo as repo
        ot1 = _mk_obj("UpdateMeta", read_roles="manager")
        repo.upsert_object_type("_test_ont_ws", ot1)
        ot2 = _mk_obj("UpdateMeta", read_roles="admin")  # 改 read_roles
        repo.upsert_object_type("_test_ont_ws", ot2)
        loaded = repo.load_registry("_test_ont_ws")
        assert loaded.object_types["UpdateMeta"].read_roles == "admin"

    def test_delete_object_type_cascade_properties(self, pg_ready):
        from engine import pg_ontology_repo as repo
        ot = _mk_obj("DeleteMe")
        repo.upsert_object_type("_test_ont_ws", ot)
        # 确认 properties 存在
        from engine import db
        props_before = db.query(
            "SELECT * FROM object_type_properties "
            "WHERE workspace_name=%s AND object_type_name=%s",
            ("_test_ont_ws", "DeleteMe"))
        assert len(props_before) >= 1
        # 删
        ok = repo.delete_object_type("_test_ont_ws", "DeleteMe")
        assert ok is True
        # properties 子表应 cascade 删除
        props_after = db.query(
            "SELECT * FROM object_type_properties "
            "WHERE workspace_name=%s AND object_type_name=%s",
            ("_test_ont_ws", "DeleteMe"))
        assert props_after == []

    def test_delete_nonexistent_returns_false(self, pg_ready):
        from engine import pg_ontology_repo as repo
        assert repo.delete_object_type("_test_ont_ws", "DoesNotExist") is False

    def test_list_object_types(self, pg_ready):
        from engine import pg_ontology_repo as repo
        repo.upsert_object_type("_test_ont_ws", _mk_obj("ListA"))
        repo.upsert_object_type("_test_ont_ws", _mk_obj("ListB"))
        result = repo.list_object_types("_test_ont_ws")
        names = {r["id"] for r in result}
        assert {"ListA", "ListB"}.issubset(names)
        # 应含 properties 字段
        list_a = next(r for r in result if r["id"] == "ListA")
        assert len(list_a["properties"]) >= 1


class TestLinkTypeCRUD:

    def test_upsert_then_load(self, pg_ready):
        from engine import pg_ontology_repo as repo
        from engine.parser import LinkType
        lt = LinkType(
            id="has_foo", label="有 Foo (has foo)", label_zh="有 Foo",
            comment="测试 Link", domain="Bar", range="Foo", via="foo_id",
            use_roles="manager", use_except="clerk")
        repo.upsert_link_type("_test_ont_ws", lt)
        loaded = repo.load_registry("_test_ont_ws")
        assert "has_foo" in loaded.link_types
        got = loaded.link_types["has_foo"]
        assert got.domain == "Bar"
        assert got.via == "foo_id"
        assert got.use_roles == "manager"
        assert got.use_except == "clerk"

    def test_delete_link_type(self, pg_ready):
        from engine import pg_ontology_repo as repo
        from engine.parser import LinkType
        lt = LinkType(id="del_link", label="x", domain="A", range="B", via="b_id")
        repo.upsert_link_type("_test_ont_ws", lt)
        assert repo.delete_link_type("_test_ont_ws", "del_link") is True
        loaded = repo.load_registry("_test_ont_ws")
        assert "del_link" not in loaded.link_types


class TestActionTypeCRUD:

    def test_upsert_then_load(self, pg_ready):
        from engine import pg_ontology_repo as repo
        from engine.action_loader import ActionDefinition
        at = ActionDefinition(
            api_name="test_action", display_name="测试动作", description="测试",
            status="active", target_object_type="TestObj",
            edits_object_types=["TestObj"], locator_field="test_id",
            parameters=[{"name": "test_id", "type": "string", "required": True}],
            submission_criteria={"roles": ["admin"], "conditions": []},
            side_effects=[{"type": "update_object", "object_type": "TestObj"}],
        )
        repo.upsert_action_type("_test_ont_ws", at)
        loaded = repo.load_registry("_test_ont_ws")
        assert "test_action" in loaded.action_types
        got = loaded.action_types["test_action"]
        assert got.target_object_type == "TestObj"
        assert got.edits_object_types == ["TestObj"]
        assert len(got.parameters) == 1
        assert got.parameters[0]["name"] == "test_id"
        assert got.submission_criteria.get("roles") == ["admin"]
        assert len(got.side_effects) == 1

    def test_delete_action_type(self, pg_ready):
        from engine import pg_ontology_repo as repo
        from engine.action_loader import ActionDefinition
        at = ActionDefinition(
            api_name="del_act", display_name="x", description="",
            status="active", target_object_type="X",
            edits_object_types=[], parameters=[],
            submission_criteria={}, side_effects=[])
        repo.upsert_action_type("_test_ont_ws", at)
        assert repo.delete_action_type("_test_ont_ws", "del_act") is True
        loaded = repo.load_registry("_test_ont_ws")
        assert "del_act" not in loaded.action_types


class TestLoadRegistryEmpty:

    def test_load_empty_workspace(self, pg_ready):
        from engine import pg_ontology_repo as repo
        loaded = repo.load_registry("_test_ont_ws_empty")
        assert len(loaded.object_types) == 0
        assert len(loaded.link_types) == 0
        assert len(loaded.action_types) == 0
