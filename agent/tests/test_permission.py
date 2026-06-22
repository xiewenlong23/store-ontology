"""WP5 PermissionEvaluator 求值引擎测试。

验证设计文档 §2.5/§4：
- 求值顺序：system_admin 短路 → Grant override → TTL 正反向 → allow-by-default
- 5 类资源：tool / object_type / property / action / link
- 正反向：roles 正向 / except 反向 / 同时声明 = roles - except
- deny 永远赢过 allow
- 属性级：readable_properties / denied_properties / can_write_property
- org_tree.py：descendants/ancestors/visible_units + load_org_tree_from_data_dir
- 工厂 build_evaluator_from_workspace
"""
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from engine.permission import (
    PermissionEvaluator, PermissionResult, GrantRow,
    eval_role_rule, build_evaluator_from_workspace, require,
    _EmptyRegistry,
)
from engine.errors import PermissionDenied
from engine.org_tree import OrgTree, OrgUnitNode, load_org_tree_from_data_dir, resolve_visible_units


# ============ eval_role_rule 单元（正反向语义）============

class TestEvalRoleRule:

    def test_empty_returns_none(self):
        """roles 与 except 都空 → None（未裁决，交下层 allow-by-default）。"""
        assert eval_role_rule("alice", "", "") is None

    def test_positive_allow(self):
        """roles 含 actor → True。"""
        assert eval_role_rule("manager", "manager, clerk", "") is True

    def test_positive_deny(self):
        """roles 非空但 actor 不在内 → False。"""
        assert eval_role_rule("clerk", "manager", "") is False

    def test_negative_except_hits(self):
        """actor 在 except → False（反向优先）。"""
        assert eval_role_rule("clerk", "manager, clerk", "clerk") is False

    def test_negative_except_only_allow(self):
        """roles 空 + except 非空 → 除 except 外都允许。"""
        assert eval_role_rule("manager", "", "clerk") is True
        assert eval_role_rule("clerk", "", "clerk") is False

    def test_wildcard_roles(self):
        """roles == "*" → 所有角色允许；except 仍可拒特定角色。"""
        assert eval_role_rule("anyone", "*", "") is True
        # actor 命中 except → 拒绝（即便 roles=*）
        assert eval_role_rule("bad_role", "*", "bad_role") is False
        # actor 不在 except → 允许
        assert eval_role_rule("anyone", "*", "bad_role") is True


# ============ 构造测试用 registry/manifest ============

def _build_evaluator(object_types=None, link_types=None, grants=None, manifest=None):
    """用内存数据构造 evaluator（避免依赖真实 workspace）。"""
    reg = _EmptyRegistry()
    reg.object_types = object_types or {}
    reg.link_types = link_types or {}
    return PermissionEvaluator(
        registry=reg, grants=grants or [], tool_manifest=manifest or {})


def _mk_obj_type(name, read_roles="", read_except="",
                 write_roles="", write_except="", props=None):
    """构造模拟 ObjectType（轻量，只含 permission.py 用到的字段）。"""
    from engine.parser import ObjectType, PropertyDef
    return ObjectType(
        id=name, label=name, comment="", properties=props or [],
        storage_file=f"{name}.json",
        read_roles=read_roles, read_except=read_except,
        write_roles=write_roles, write_except=write_except)


def _mk_prop(name, read_roles="", read_except="",
             write_roles="", write_except=""):
    from engine.parser import PropertyDef
    return PropertyDef(
        name=name, type="string",
        read_roles=read_roles, read_except=read_except,
        write_roles=write_roles, write_except=write_except)


# ============ Object 级求值 ============

class TestObjectLevel:

    def test_system_admin_short_circuit(self):
        e = _build_evaluator(object_types={
            "Secret": _mk_obj_type("Secret", read_roles="")  # 无人可读
        })
        r = e.can_read_object("system_admin", "Secret")
        assert r.granted is True
        assert "system_admin" in r.reason

    def test_read_allow_by_default(self):
        """未声明权限 → allow-by-default。"""
        e = _build_evaluator(object_types={
            "Foo": _mk_obj_type("Foo")
        })
        assert e.can_read_object("any_role", "Foo").granted is True

    def test_read_positive_allow(self):
        e = _build_evaluator(object_types={
            "Foo": _mk_obj_type("Foo", read_roles="manager, clerk")
        })
        assert e.can_read_object("manager", "Foo").granted is True
        assert e.can_read_object("clerk", "Foo").granted is True

    def test_read_positive_deny(self):
        e = _build_evaluator(object_types={
            "Foo": _mk_obj_type("Foo", read_roles="manager")
        })
        r = e.can_read_object("clerk", "Foo")
        assert r.granted is False
        assert r.denied_at == "ttl"

    def test_read_except_overrides(self):
        e = _build_evaluator(object_types={
            "Foo": _mk_obj_type("Foo", read_roles="*", read_except="clerk")
        })
        assert e.can_read_object("manager", "Foo").granted is True
        assert e.can_read_object("clerk", "Foo").granted is False

    def test_unknown_object_allow_by_default(self):
        e = _build_evaluator()
        assert e.can_read_object("any", "NotExist").granted is True


# ============ Grant override ============

class TestGrantOverride:

    def test_grant_allow_overrides_ttl_deny(self):
        """Grant allow 覆盖 TTL 拒绝。"""
        e = _build_evaluator(
            object_types={"Foo": _mk_obj_type("Foo", read_roles="manager")},
            grants=[GrantRow(role_id="clerk", resource_type="object_type",
                             resource_id="Foo", action="read", effect="allow")])
        assert e.can_read_object("clerk", "Foo").granted is True

    def test_grant_deny_overrides_ttl_allow(self):
        """Grant deny 覆盖 TTL 允许（deny 优先）。"""
        e = _build_evaluator(
            object_types={"Foo": _mk_obj_type("Foo", read_roles="*")},
            grants=[GrantRow(role_id="clerk", resource_type="object_type",
                             resource_id="Foo", action="read", effect="deny")])
        assert e.can_read_object("clerk", "Foo").granted is False
        assert e.can_read_object("clerk", "Foo").denied_at == "grant"

    def test_grant_deny_overrides_grant_allow(self):
        """同样命中时 deny 赢 allow。"""
        e = _build_evaluator(
            object_types={"Foo": _mk_obj_type("Foo")},
            grants=[
                GrantRow(role_id="clerk", resource_type="object_type",
                         resource_id="Foo", action="read", effect="allow"),
                GrantRow(role_id="clerk", resource_type="object_type",
                         resource_id="Foo", action="read", effect="deny"),
            ])
        assert e.can_read_object("clerk", "Foo").granted is False

    def test_grant_wildcard_resource(self):
        """Grant resource_id == "*" 匹配任意。"""
        e = _build_evaluator(
            grants=[GrantRow(role_id="clerk", resource_type="object_type",
                             resource_id="*", action="read", effect="deny")])
        assert e.can_read_object("clerk", "AnyObj").granted is False


# ============ Tool 级 ============

class TestToolLevel:

    def test_tool_from_manifest_allow(self):
        from engine.tool_manifest import ToolPerm
        e = _build_evaluator(manifest={
            "query_foo": ToolPerm(name="query_foo", use_roles="manager")
        })
        assert e.can_use_tool("manager", "query_foo").granted is True
        assert e.can_use_tool("clerk", "query_foo").granted is False

    def test_tool_not_in_manifest_allow_by_default(self):
        e = _build_evaluator()
        assert e.can_use_tool("any", "any_tool").granted is True

    def test_tool_wildcard_roles(self):
        from engine.tool_manifest import ToolPerm
        e = _build_evaluator(manifest={
            "execute_action": ToolPerm(name="execute_action", use_roles="*")
        })
        for role in ["clerk", "manager", "any"]:
            assert e.can_use_tool(role, "execute_action").granted is True


# ============ 属性级 ============

class TestPropertyLevel:

    def test_readable_properties_all_when_no_restrictions(self):
        """无属性级声明 → 全部可读。"""
        e = _build_evaluator(object_types={
            "Emp": _mk_obj_type("Emp", props=[
                _mk_prop("id"), _mk_prop("name"), _mk_prop("salary")
            ])
        })
        readable = e.readable_properties("clerk", "Emp")
        assert readable == {"id", "name", "salary"}

    def test_readable_properties_masks_denied(self):
        """属性 read_except 命中 → 该属性被 mask。"""
        e = _build_evaluator(object_types={
            "Emp": _mk_obj_type("Emp", read_roles="*", props=[
                _mk_prop("id"), _mk_prop("name"),
                _mk_prop("salary", read_except="clerk"),
                _mk_prop("password_hash", read_except="*"),  # 全员除外 = 无人可读
            ])
        })
        readable = e.readable_properties("clerk", "Emp")
        assert "id" in readable
        assert "name" in readable
        assert "salary" not in readable
        assert "password_hash" not in readable

    def test_denied_properties_for_hint(self):
        """denied_properties 返回不可读集合（用于响应文本提示）。"""
        e = _build_evaluator(object_types={
            "Emp": _mk_obj_type("Emp", read_roles="*", props=[
                _mk_prop("salary", read_except="clerk"),
                _mk_prop("password_hash", read_except="*"),   # 全员除外
            ])
        })
        denied = e.denied_properties("clerk", "Emp")
        assert denied == {"salary", "password_hash"}

    def test_object_denied_returns_empty_readable(self):
        """Object 级 read 被拒 → readable_properties 空集合。"""
        e = _build_evaluator(object_types={
            "Secret": _mk_obj_type("Secret", read_roles="manager", props=[
                _mk_prop("data")
            ])
        })
        assert e.readable_properties("clerk", "Secret") == set()

    def test_can_write_property(self):
        e = _build_evaluator(object_types={
            "Foo": _mk_obj_type("Foo", props=[
                _mk_prop("status", write_roles="manager"),
            ])
        })
        assert e.can_write_property("manager", "Foo", "status").granted is True
        assert e.can_write_property("clerk", "Foo", "status").granted is False


# ============ Link / Action 级 ============

class TestLinkActionLevel:

    def test_can_traverse_link(self):
        from engine.parser import LinkType
        lt = LinkType(id="has_emp", label="x", domain="Store", range="Emp",
                      via="store_id", use_roles="manager")
        e = _build_evaluator(link_types={"has_emp": lt})
        assert e.can_traverse_link("manager", "has_emp").granted is True
        assert e.can_traverse_link("clerk", "has_emp").granted is False

    def test_can_execute_action_default_allow(self):
        """Action 无 TTL 元数据 → allow-by-default（submission_criteria 仍校验角色）。"""
        e = _build_evaluator()
        assert e.can_execute_action("any", "any_action").granted is True


# ============ require helper ============

class TestRequire:

    def test_require_allow_noop(self):
        require(PermissionResult.allow(), "测试")

    def test_require_deny_raises(self):
        with pytest.raises(PermissionDenied, match="无权"):
            require(PermissionResult.deny("x", "ttl"), "测试")


# ============ OrgTree ============

class TestOrgTree:

    def _build_test_tree(self):
        """构造 3 级测试树：root → region → store_001/store_002。"""
        return OrgTree([
            OrgUnitNode(id="root", parent_id=None, level="brand"),
            OrgUnitNode(id="region_north", parent_id="root", level="region"),
            OrgUnitNode(id="store_001", parent_id="region_north", level="store"),
            OrgUnitNode(id="store_002", parent_id="region_north", level="store"),
        ])

    def test_descendants_includes_self_and_children(self):
        t = self._build_test_tree()
        assert set(t.descendants("region_north")) == {"region_north", "store_001", "store_002"}
        assert set(t.descendants("store_001")) == {"store_001"}

    def test_ancestors_chain_to_root(self):
        t = self._build_test_tree()
        assert t.ancestors("store_001") == ["store_001", "region_north", "root"]

    def test_visible_units(self):
        t = self._build_test_tree()
        assert t.visible_units("region_north") == {"region_north", "store_001", "store_002"}

    def test_unknown_unit_empty(self):
        t = self._build_test_tree()
        assert t.descendants("not_exist") == []
        assert t.ancestors("not_exist") == []

    def test_load_from_data_dir(self, tmp_path):
        """从 org_units.json 加载。"""
        (tmp_path / "org_units.json").write_text(json.dumps([
            {"id": "a", "parent_id": None, "level": "brand"},
            {"id": "b", "parent_id": "a", "level": "store"},
        ], ensure_ascii=False), encoding="utf-8")
        t = load_org_tree_from_data_dir(str(tmp_path))
        assert t is not None
        assert t.visible_units("a") == {"a", "b"}

    def test_load_missing_file_returns_none(self, tmp_path):
        assert load_org_tree_from_data_dir(str(tmp_path)) is None

    def test_resolve_visible_units_wildcard(self):
        """'*' → 空集合（调用方判断 '*' = 总部全可见）。"""
        assert resolve_visible_units("*", None) == set()

    def test_resolve_visible_units_fallback_no_tree(self):
        """org_tree 为 None → 回落精确匹配（只含自身）。"""
        assert resolve_visible_units("store_001", None) == {"store_001"}

    def test_resolve_visible_units_with_tree(self):
        t = self._build_test_tree()
        assert resolve_visible_units("region_north", t) == \
            {"region_north", "store_001", "store_002"}


# ============ 工厂 build_evaluator_from_workspace ============

class TestBuildEvaluatorFromWorkspace:

    def test_unknown_workspace_returns_empty_evaluator(self):
        from engine import pack as pack_mod
        from engine.bootstrap import bootstrap
        pack_mod.clear_workspace_dirs()
        try:
            e = build_evaluator_from_workspace("does_not_exist")
            # 空 evaluator → 全 allow-by-default
            assert e.can_read_object("any", "Any").granted is True
        finally:
            # 恢复真实 workspace 注册（reload 强制重跑 register_workspace_dir）
            import importlib
            import sys
            pack_mod.clear_workspace_dirs()
            bootstrap()
            for ws_name in ["retail", "jjy", "customerA"]:
                mod_name = f"workspace.{ws_name}.workspace"
                if mod_name in sys.modules:
                    importlib.reload(sys.modules[mod_name])

    def test_build_from_real_retail_workspace(self):
        """从 retail workspace 构建 evaluator，验证 identity TTL 的权限元数据生效。"""
        from engine import pack as pack_mod
        from engine.bootstrap import bootstrap
        # 恢复注册（其他测试可能 clear 后未恢复）
        pack_mod.clear_workspace_dirs()
        bootstrap()
        import importlib
        import sys
        if pack_mod.get_workspace_dir("retail") is None:
            for ws_name in ["retail", "jjy", "customerA"]:
                mod_name = f"workspace.{ws_name}.workspace"
                if mod_name in sys.modules:
                    importlib.reload(sys.modules[mod_name])
        try:
            e = build_evaluator_from_workspace("retail")
            # User.read_roles="system_admin" → clerk 不可读
            r = e.can_read_object("store_clerk", "User")
            assert r.granted is False
            # system_admin 短路
            assert e.can_read_object("system_admin", "User").granted is True
        finally:
            pack_mod.clear_workspace_dirs()
            bootstrap()
            for ws_name in ["retail", "jjy", "customerA"]:
                mod_name = f"workspace.{ws_name}.workspace"
                if mod_name in sys.modules:
                    importlib.reload(sys.modules[mod_name])
