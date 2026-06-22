"""WP5 接入收尾：PermissionEvaluator 真正接入 tool 管道的测试。

验证 5 个内核工具调 PermissionEvaluator：
- query_entity: Object 级读 + 属性级 mask + 文本提示
- traverse_relation: Link 级遍历校验
- execute_action / confirm_action: tool 级 + action 级校验
- create_entity / update_entity: tool 级 + Object 写 + 属性写校验

用 monkeypatch 替换 _get_actor / _get_evaluator / _get_repo / _get_executor，
隔离测试权限路径，不依赖真实 workspace 装配。
"""
import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import agent.tools.shared as shared
from agent.tools.query_tools import query_entity, traverse_relation, query_task
from agent.tools.action_tools import execute_action, confirm_action
from agent.tools.crud_tools import create_entity, update_entity, update_task


def _extract_data(text):
    """从 tool 返回文本提取 COPILOTKIT_DATA json。"""
    import re
    m = re.search(r'<!--COPILOTKIT_DATA-->\n?([\s\S]*?)\n?<!--/COPILOTKIT_DATA-->', text)
    return json.loads(m.group(1)) if m else None


def _setup_all(monkeypatch, *, role="system_admin", repo_rows=None,
                evaluator=None, executor=None):
    """统一 monkeypatch：actor / evaluator / repo / executor / parser。

    role: 模拟的 actor.role
    repo_rows: {entity_type: [records]} 模拟 repo 数据
    evaluator: 自定义 PermissionEvaluator（None 时全 allow-by-default 空 evaluator）
    executor: 自定义 executor（None 时抛错占位）
    """
    from engine.permission import PermissionEvaluator, _EmptyRegistry
    from engine.tenant import TenantContext

    monkeypatch.setattr(shared, "_get_actor", lambda tenant=None: {"role": role})
    monkeypatch.setattr(shared, "_get_evaluator",
                        lambda: evaluator or PermissionEvaluator(
                            registry=_EmptyRegistry(), grants=[], tool_manifest={}))
    monkeypatch.setattr(shared, "_tc_ctx",
                        lambda ws=None, org=None: TenantContext(workspace_name="_test", org_unit_id="*"))

    # repo：用最小 fake，支持 read/read_one/write
    class _FakeRepo:
        def __init__(self, rows):
            self._rows = rows or {}
            self.written = []
        def read(self, et, tc, filters=None):
            rows = list(self._rows.get(et, []))
            if filters:
                rows = [r for r in rows
                        if all(str(r.get(k)) == str(v) for k, v in filters.items())]
            return rows
        def read_one(self, et, tc, eid):
            for r in self._rows.get(et, []):
                if r.get("id") == eid:
                    return r
            return None
        def write(self, et, tc, rec, create=False, bypass_action_check=False):
            self.written.append((et, rec))
            return rec

    fake_repo = _FakeRepo(repo_rows or {})
    monkeypatch.setattr(shared, "_get_repo", lambda tc=None, vertical=None: fake_repo)

    # parser：返回 registry（用于 query_entity 检查实体类型存在）
    class _FakeParser:
        class _Reg:
            object_types = {"Foo": "OBJ_FOO", "Bar": "OBJ_BAR"}
            link_types = {"has_bar": "LINK_HAS_BAR"}
        registry = _Reg()
    monkeypatch.setattr(shared, "_parser", lambda vertical=None: _FakeParser())

    # executor
    monkeypatch.setattr(shared, "_get_executor", lambda vertical=None, process_name=None: executor)

    # preview_cache：fake（put/get）
    class _FakeCache:
        def __init__(self):
            self.store = {}
            self._seq = 0
        def put(self, preview):
            self._seq += 1
            pid = f"pid_{self._seq}"
            self.store[pid] = preview
            return pid
        def get(self, pid):
            return self.store.get(pid)
    monkeypatch.setattr(shared, "_preview_cache", _FakeCache())

    return fake_repo


def _build_obj_type(name, read_roles="", read_except="",
                    write_roles="", write_except="", props=None):
    from engine.parser import ObjectType, PropertyDef
    return ObjectType(
        id=name, label=name, comment="", properties=props or [],
        storage_file=f"{name}.json",
        read_roles=read_roles, read_except=read_except,
        write_roles=write_roles, write_except=write_except)


def _build_prop(name, read_roles="", read_except="",
                write_roles="", write_except=""):
    from engine.parser import PropertyDef
    return PropertyDef(
        name=name, type="string",
        read_roles=read_roles, read_except=read_except,
        write_roles=write_roles, write_except=write_except)


def _evaluator_with(object_types, link_types=None, grants=None, manifest=None):
    """用内存数据构造 evaluator。"""
    from engine.permission import PermissionEvaluator, _EmptyRegistry
    reg = _EmptyRegistry()
    reg.object_types = object_types or {}
    reg.link_types = link_types or {}
    return PermissionEvaluator(
        registry=reg, grants=grants or [], tool_manifest=manifest or {})


# ============ query_entity：Object 级读 ============

class TestQueryEntityObjectLevel:

    def test_read_denied_returns_permission_denied(self, monkeypatch):
        """Object 级 read_roles 不含 actor → 拒绝。"""
        ev = _evaluator_with({
            "Foo": _build_obj_type("Foo", read_roles="manager")
        })
        _setup_all(monkeypatch, role="clerk", evaluator=ev,
                   repo_rows={"Foo": [{"id": "f1", "name": "x"}]})
        out = query_entity.invoke({"entity_type": "Foo"})
        data = _extract_data(out)
        assert data["total"] == 0
        assert data["permission_denied"] is True
        assert "无权访问 Foo" in out

    def test_read_allowed_returns_rows(self, monkeypatch):
        ev = _evaluator_with({"Foo": _build_obj_type("Foo")})
        _setup_all(monkeypatch, role="clerk", evaluator=ev,
                   repo_rows={"Foo": [{"id": "f1", "name": "x", "secret": "s"}]})
        out = query_entity.invoke({"entity_type": "Foo"})
        data = _extract_data(out)
        assert data["total"] == 1
        assert data["items"][0]["id"] == "f1"


# ============ query_entity：属性级 mask ============

class TestQueryEntityPropertyMask:

    def test_denied_property_masked_with_hint(self, monkeypatch):
        """属性级 read_except 命中 → 字段从返回中 mask + 文本提示。"""
        ev = _evaluator_with({
            "Foo": _build_obj_type("Foo", read_roles="*",
                props=[_build_prop("id"), _build_prop("name"),
                       _build_prop("salary", read_except="clerk")])
        })
        _setup_all(monkeypatch, role="clerk", evaluator=ev,
                   repo_rows={"Foo": [{"id": "f1", "name": "Alice", "salary": 5000}]})
        out = query_entity.invoke({"entity_type": "Foo"})
        data = _extract_data(out)
        item = data["items"][0]
        assert "salary" not in item, "salary 应被 mask"
        assert item["name"] == "Alice"
        assert "salary" in data["masked_fields"]
        assert "已隐去" in out and "salary" in out

    def test_no_restriction_no_mask(self, monkeypatch):
        """无属性级声明 → 不 mask。"""
        ev = _evaluator_with({
            "Foo": _build_obj_type("Foo", read_roles="*",
                props=[_build_prop("id"), _build_prop("salary")])
        })
        _setup_all(monkeypatch, role="clerk", evaluator=ev,
                   repo_rows={"Foo": [{"id": "f1", "salary": 5000}]})
        out = query_entity.invoke({"entity_type": "Foo"})
        data = _extract_data(out)
        assert data["items"][0]["salary"] == 5000
        assert data["masked_fields"] == []


# ============ traverse_relation：Link 级 ============

class TestTraverseRelation:

    def test_link_denied(self, monkeypatch):
        from engine.parser import LinkType
        lt = LinkType(id="has_bar", label="x", domain="Foo", range="Bar",
                      via="bar_id", use_roles="manager")
        ev = _evaluator_with({"Foo": _build_obj_type("Foo")},
                             link_types={"has_bar": lt})
        _setup_all(monkeypatch, role="clerk", evaluator=ev,
                   repo_rows={"Foo": [{"id": "f1", "bar_id": "b1"}]})
        out = traverse_relation.invoke(
            {"source_type": "Foo", "source_id": "f1", "relation": "has_bar"})
        data = _extract_data(out)
        assert data["total"] == 0
        assert data["permission_denied"] is True


# ============ execute_action / confirm_action ============

class TestExecuteAction:

    def test_tool_level_denied(self, monkeypatch):
        """manifest 锁 execute_action 为 admin → clerk 拒绝。"""
        from engine.tool_manifest import ToolPerm
        ev = _evaluator_with({},
                             manifest={"execute_action": ToolPerm(
                                 name="execute_action", use_roles="system_admin")})
        _setup_all(monkeypatch, role="clerk", evaluator=ev)
        out = execute_action.invoke(
            {"action_type": "create_foo", "params": {}})
        data = _extract_data(out)
        assert data["valid"] is False
        assert data["permission_denied"] is True

    def test_action_allowed_generates_preview(self, monkeypatch):
        """无 manifest 声明 → allow-by-default → 进入正常 action 流程。"""
        ev = _evaluator_with({})

        class _FakeAction:
            parameters = []
        class _FakeExec:
            actions = {"create_foo": _FakeAction()}
            def validate(self, at, params):
                return params

        _setup_all(monkeypatch, role="clerk", evaluator=ev,
                   executor=_FakeExec())
        out = execute_action.invoke(
            {"action_type": "create_foo", "params": {"x": 1}})
        data = _extract_data(out)
        assert data["valid"] is True
        assert "preview_id" in data


# ============ create_entity / update_entity ============

class TestCrudPermission:

    def test_create_denied_by_tool_manifest(self, monkeypatch):
        from engine.tool_manifest import ToolPerm
        ev = _evaluator_with({},
                             manifest={"create_entity": ToolPerm(
                                 name="create_entity", use_roles="system_admin")})
        _setup_all(monkeypatch, role="clerk", evaluator=ev)
        out = create_entity.invoke({"entity_type": "Foo"})
        data = _extract_data(out)
        assert data["success"] is False
        assert data["permission_denied"] is True

    def test_create_denied_by_object_write(self, monkeypatch):
        """tool 级过但 Object 级 write_roles 不含 actor → 拒绝。"""
        ev = _evaluator_with({
            "Foo": _build_obj_type("Foo", write_roles="manager")
        })
        _setup_all(monkeypatch, role="clerk", evaluator=ev)
        out = create_entity.invoke({"entity_type": "Foo"})
        data = _extract_data(out)
        assert data["success"] is False
        assert "无权创建 Foo" in out

    def test_update_property_denied(self, monkeypatch):
        """update_entity 的字段级写校验。

        注：update_entity 用 **kwargs，langchain @tool schema 不支持自由 kwargs，
        故直接调 .func 绕过 schema 校验，验证权限路径。
        """
        ev = _evaluator_with({
            "Foo": _build_obj_type("Foo", write_roles="*",
                props=[_build_prop("status", write_roles="manager")])
        })
        _setup_all(monkeypatch, role="clerk", evaluator=ev,
                   repo_rows={"Foo": [{"id": "f1", "status": "old"}]})
        # 直接调底层函数，传 status 字段
        out = update_entity.func(
            "Foo", "f1", None, "*", status="new")
        data = _extract_data(out)
        assert data["success"] is False
        assert data["denied_field"] == "status"


# ============ update_task：tool 级 ============

class TestUpdateTaskPermission:

    def test_update_task_denied_by_manifest(self, monkeypatch):
        from engine.tool_manifest import ToolPerm
        ev = _evaluator_with({},
                             manifest={"update_task": ToolPerm(
                                 name="update_task", use_roles="system_admin")})
        _setup_all(monkeypatch, role="clerk", evaluator=ev)
        out = update_task.invoke({"task_id": "t1", "notes": "x"})
        data = _extract_data(out)
        assert data["success"] is False
        assert data["permission_denied"] is True
