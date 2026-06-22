"""WP7 admin_ontology_api 测试。

JSON dict → dataclass 转换器 round-trip：与 pg_ontology_repo.list_* 的输出结构对称，
保证前端 GET 拿到的对象 POST/PUT 回去能复原（spec §3.2）。
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from engine.admin_ontology_api import (
    json_to_object_type, json_to_link_type, json_to_action_def,
)
from engine.parser import ObjectType, LinkType, PropertyDef
from engine.action_loader import ActionDefinition


class TestJsonObjectConv:
    def test_full_object_type(self):
        body = {
            "id": "Task", "label": "任务 (Task)", "label_zh": "任务",
            "comment": "工单", "storage_file": "tasks.json", "status": "active",
            "visibility": "normal", "edits_only_via_actions": True,
            "read_roles": "store_manager,regional_mgr",
            "read_except": "clerk",
            "write_roles": "",
            "write_except": "",
            "properties": [
                {"name": "id", "type": "string",
                 "read_roles": "", "read_except": "", "write_roles": "", "write_except": ""},
                {"name": "assignee", "type": "ref:Employee",
                 "read_roles": "store_manager", "read_except": "",
                 "write_roles": "store_manager", "write_except": ""},
            ],
        }
        ot = json_to_object_type(body)
        assert isinstance(ot, ObjectType)
        assert ot.id == "Task"
        assert ot.label == "任务 (Task)"
        assert ot.edits_only_via_actions is True
        assert ot.read_roles == "store_manager,regional_mgr"
        assert len(ot.properties) == 2
        assert ot.properties[1].name == "assignee"
        assert ot.properties[1].read_roles == "store_manager"

    def test_missing_required_raises(self):
        """body 缺 id 主键 → ValueError（端点层映射 422）。"""
        with pytest.raises(ValueError, match="id"):
            json_to_object_type({"label": "x"})

    def test_empty_properties_ok(self):
        ot = json_to_object_type({"id": "X", "label": "X", "properties": []})
        assert ot.properties == []

    def test_property_defaults(self):
        """property 子项只给 name+type，roles 字段缺省为 ""。"""
        ot = json_to_object_type({
            "id": "X", "label": "X",
            "properties": [{"name": "id", "type": "string"}],
        })
        p = ot.properties[0]
        assert p.read_roles == "" and p.write_except == ""


class TestJsonLinkConv:
    def test_full_link(self):
        body = {
            "id": "assignedTo", "label": "指派给 (assignedTo)",
            "label_zh": "指派给", "comment": "task→employee",
            "domain": "Task", "range": "Employee", "via": "assignee",
            "use_roles": "store_manager", "use_except": "",
        }
        lt = json_to_link_type(body)
        assert isinstance(lt, LinkType)
        assert lt.id == "assignedTo"
        assert lt.range == "Employee"
        assert lt.use_roles == "store_manager"

    def test_link_missing_id(self):
        with pytest.raises(ValueError, match="id"):
            json_to_link_type({"domain": "Task"})


class TestJsonActionConv:
    def test_full_action(self):
        body = {
            "api_name": "create_task", "display_name": "建工单",
            "description": "创建", "status": "active",
            "target_object_type": "Task",
            "edits_object_types": ["Task"],
            "locator_field": "task_id",
            "parameters": [{"name": "title", "type": "string"}],
            "submission_criteria": {"require_approval_from": "store_manager"},
            "side_effects": [{"kind": "audit_log"}],
        }
        ad = json_to_action_def(body)
        assert isinstance(ad, ActionDefinition)
        assert ad.api_name == "create_task"
        assert ad.parameters[0]["name"] == "title"
        assert ad.submission_criteria["require_approval_from"] == "store_manager"
        assert ad.side_effects[0]["kind"] == "audit_log"

    def test_action_missing_api_name(self):
        with pytest.raises(ValueError, match="api_name"):
            json_to_action_def({"display_name": "x"})

    def test_action_optional_fields_default(self):
        ad = json_to_action_def({"api_name": "noop"})
        assert ad.parameters == [] and ad.side_effects == []
        assert ad.submission_criteria == {}
        assert ad.target_object_type == ""


class TestRequireAdmin:
    """require_admin 鉴权逻辑。

    actor 由 _get_actor() 从 auth_ctx contextvar 派生。测试用 monkeypatch 替换。
    """

    def test_system_admin_allowed(self, monkeypatch):
        import engine.admin_ontology_api as mod
        monkeypatch.setattr(mod, "_get_actor", lambda: {"role": "system_admin",
                                                         "user_id": "u1"})
        # 不抛、不返回 JSONResponse（返回 None）
        result = mod.require_admin(ws_name="jjy", is_admin_account=False)
        assert result is None

    def test_other_role_denied(self, monkeypatch):
        import engine.admin_ontology_api as mod
        monkeypatch.setattr(mod, "_get_actor", lambda: {"role": "clerk",
                                                         "user_id": "u1"})
        result = mod.require_admin(ws_name="jjy", is_admin_account=False)
        assert result is not None
        assert result.status_code == 403

    def test_bootstrap_admin_account_allowed(self, monkeypatch):
        """username=='admin' 的 bootstrap 初始账号即使 role 非 system_admin 也放行。"""
        import engine.admin_ontology_api as mod
        monkeypatch.setattr(mod, "_get_actor", lambda: {"role": "store_manager",
                                                         "user_id": "u1"})
        result = mod.require_admin(ws_name="jjy", is_admin_account=True)
        assert result is None


# ============ WP7/WP8 端点端到端测试 ============

@pytest.fixture
def client(monkeypatch):
    """启动 FastAPI app（main:app）+ 关强制认证 + actor=system_admin。

    AUTH_REQUIRED=false → auth middleware 放行；_get_actor 兜底返回 system_admin。
    """
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql://ontology:ontology@localhost:5433/ontology")
    # 重置 workspace 实例缓存 + PG 状态，避免跨用例污染
    from engine.workspace_bootstrap import reset_instances
    from engine import db as db_mod
    reset_instances()
    db_mod._reset_pg_state()
    import main
    with TestClient(main.app) as c:
        yield c
    reset_instances()
    db_mod._reset_pg_state()


@pytest.fixture
def admin_ws(client):
    """准备测试 workspace：清空 PG 中 _test_admin_ws 的 ontology 数据。"""
    from engine import db as db_mod
    if not db_mod.ping():
        pytest.skip("PG 不可用")
    db_mod.execute("DELETE FROM object_types WHERE workspace_name = %s", ("_test_admin_ws",))
    db_mod.execute("DELETE FROM link_types WHERE workspace_name = %s", ("_test_admin_ws",))
    db_mod.execute("DELETE FROM action_types WHERE workspace_name = %s", ("_test_admin_ws",))
    yield "_test_admin_ws"
    db_mod.execute("DELETE FROM object_types WHERE workspace_name = %s", ("_test_admin_ws",))
    db_mod.execute("DELETE FROM link_types WHERE workspace_name = %s", ("_test_admin_ws",))
    db_mod.execute("DELETE FROM action_types WHERE workspace_name = %s", ("_test_admin_ws",))


@pytest.fixture
def deny_admin(monkeypatch):
    """让 require_admin 拒绝（actor=clerk）。"""
    import engine.admin_ontology_api as mod
    monkeypatch.setattr(mod, "_get_actor", lambda: {"role": "clerk", "user_id": "u1"})


HEADERS = {"X-Workspace": "_test_admin_ws"}


class TestObjectEndpoints:
    def test_post_then_get(self, client, admin_ws):
        body = {
            "id": "Foo", "label": "Foo (x)", "label_zh": "Foo",
            "comment": "t", "storage_file": "foos.json", "status": "active",
            "visibility": "normal", "edits_only_via_actions": False,
            "read_roles": "", "read_except": "", "write_roles": "", "write_except": "",
            "properties": [{"name": "id", "type": "string"},
                           {"name": "n", "type": "string"}],
        }
        r = client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                        json=body, headers=HEADERS)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["created"]["id"] == "Foo"
        # GET 确认落库
        g = client.get(f"/api/admin/customers/{admin_ws}/ontology/objects",
                       headers=HEADERS)
        ids = [o["id"] for o in g.json()["objects"]]
        assert "Foo" in ids

    def test_put_replaces_properties(self, client, admin_ws):
        # 先 POST 2 props
        client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                    json={"id": "Bar", "label": "Bar", "properties": [
                        {"name": "id", "type": "string"},
                        {"name": "a", "type": "string"}]},
                    headers=HEADERS)
        # PUT 改成 3 props
        r = client.put(f"/api/admin/customers/{admin_ws}/ontology/objects/Bar",
                       json={"id": "Bar", "label": "Bar2", "properties": [
                           {"name": "id", "type": "string"},
                           {"name": "a", "type": "string"},
                           {"name": "b", "type": "string"}]},
                       headers=HEADERS)
        assert r.status_code == 200
        # GET 验证 3 props + label 更新
        g = client.get(f"/api/admin/customers/{admin_ws}/ontology/objects",
                       headers=HEADERS)
        bar = next(o for o in g.json()["objects"] if o["id"] == "Bar")
        assert bar["label"] == "Bar2"
        assert len(bar["properties"]) == 3

    def test_delete_then_404(self, client, admin_ws):
        client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                    json={"id": "Baz", "label": "Baz", "properties": []},
                    headers=HEADERS)
        d = client.delete(f"/api/admin/customers/{admin_ws}/ontology/objects/Baz",
                          headers=HEADERS)
        assert d.status_code == 200
        assert d.json()["deleted"] is True
        d2 = client.delete(f"/api/admin/customers/{admin_ws}/ontology/objects/Baz",
                           headers=HEADERS)
        assert d2.status_code == 404

    def test_post_denied_non_admin(self, client, admin_ws, deny_admin):
        r = client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                        json={"id": "X", "label": "X", "properties": []},
                        headers=HEADERS)
        assert r.status_code == 403

    def test_invalid_body_422(self, client, admin_ws):
        r = client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                        json={"label": "no id"}, headers=HEADERS)
        assert r.status_code == 422


class TestLinkActionEndpoints:
    def test_link_crud(self, client, admin_ws):
        r = client.post(f"/api/admin/customers/{admin_ws}/ontology/links",
                        json={"id": "lk", "label": "lk", "domain": "A",
                              "range": "B", "via": "ref", "use_roles": "x"},
                        headers=HEADERS)
        assert r.status_code == 200
        d = client.delete(f"/api/admin/customers/{admin_ws}/ontology/links/lk",
                          headers=HEADERS)
        assert d.status_code == 200

    def test_action_crud(self, client, admin_ws):
        r = client.post(f"/api/admin/customers/{admin_ws}/ontology/actions",
                        json={"api_name": "do_x", "display_name": "Do X",
                              "target_object_type": "Task",
                              "parameters": [{"name": "a", "type": "string"}]},
                        headers=HEADERS)
        assert r.status_code == 200
        d = client.delete(f"/api/admin/customers/{admin_ws}/ontology/actions/do_x",
                          headers=HEADERS)
        assert d.status_code == 200


class TestInvalidation:
    def test_post_invalidates_workspace_instance(self, client, admin_ws):
        """编辑后 bootstrap_workspace 重取应反映新对象（spec §7 test 6）。"""
        from engine.workspace_bootstrap import bootstrap_workspace, invalidate_workspace
        # 触发一次 bootstrap 缓存（此时 _test_admin_ws 的 registry 为空）
        invalidate_workspace(admin_ws)
        inst_before = bootstrap_workspace(admin_ws)
        assert "Foo" not in inst_before.registry.object_types
        # POST 新对象
        client.post(f"/api/admin/customers/{admin_ws}/ontology/objects",
                    json={"id": "Foo", "label": "Foo", "properties": []},
                    headers=HEADERS)
        # 再取（端点内部应已 invalidate）
        inst_after = bootstrap_workspace(admin_ws)
        assert "Foo" in inst_after.registry.object_types


