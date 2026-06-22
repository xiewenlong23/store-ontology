"""WP4a 测试：pack.py 的 domain kind 校验 + 新增枚举。

验证设计文档 §5 WP4a：
- CapabilityDomain.kind 字段（默认 business）
- WorkspaceDef.required_domain_kinds 默认 4 类必备
- register_workspace_dir 校验：缺必备 kind → ValueError；含全部 → 通过
- 自动推断：kind=business 但 name 在标准名集合里 → 视为该 kind
- schemas.py 新增 OrgUnitLevel/CategoryLevel 枚举
"""
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from engine.pack import (
    CapabilityDomain, ValueChainProcess, WorkspaceDef,
    register_workspace_dir, clear_workspace_dirs, get_workspace_dir,
    REQUIRED_DOMAIN_KINDS, REQUIRED_OBJECTS_BY_KIND,
)
from engine.schemas import OrgUnitLevel, CategoryLevel


def _mk_domain(name, kind="business"):
    """构造一个 CapabilityDomain（ttl_path/actions_dir 用占位路径）。"""
    return CapabilityDomain(
        name=name, display_name=name,
        ttl_path=f"/tmp/{name}.ttl", actions_dir=f"/tmp/{name}_actions",
        kind=kind)


class TestCapabilityDomainKind:

    def test_default_kind_is_business(self):
        d = _mk_domain("foo")
        assert d.kind == "business"

    def test_kind_can_be_set(self):
        d = _mk_domain("org", kind="organization")
        assert d.kind == "organization"


class TestRequiredDomainKinds:

    def test_required_default_is_four(self):
        ws = WorkspaceDef(name="x", display_name="x")
        assert ws.required_domain_kinds == ["organization", "personnel", "category", "identity"]

    def test_can_disable_for_tests(self):
        ws = WorkspaceDef(name="x", display_name="x", required_domain_kinds=[])
        assert ws.required_domain_kinds == []


class TestRegisterValidation:

    def setup_method(self):
        clear_workspace_dirs()

    def teardown_method(self):
        clear_workspace_dirs()

    def test_register_rejects_missing_kinds(self):
        """缺必备 kind → ValueError。"""
        ws = WorkspaceDef(
            name="bad", display_name="bad",
            domains=[_mk_domain("organization")],   # 只有 organization
            required_domain_kinds=["organization", "personnel", "category", "identity"])
        with pytest.raises(ValueError, match="缺必备 domain kind"):
            register_workspace_dir(ws)

    def test_register_accepts_all_kinds_explicit(self):
        """显式 kind 含 4 类 → 通过。"""
        ws = WorkspaceDef(
            name="ok1", display_name="ok1",
            domains=[
                _mk_domain("org_x", kind="organization"),
                _mk_domain("hr_x", kind="personnel"),
                _mk_domain("cat_x", kind="category"),
                _mk_domain("id_x", kind="identity"),
            ])
        register_workspace_dir(ws)
        assert get_workspace_dir("ok1") is ws

    def test_register_accepts_standard_name_autoinfer(self):
        """kind 默认 business 但 name 是标准名 → 自动推断。"""
        ws = WorkspaceDef(
            name="ok2", display_name="ok2",
            domains=[
                _mk_domain("organization"),   # 默认 business 但 name 命中
                _mk_domain("personnel"),
                _mk_domain("category"),
                _mk_domain("identity"),
            ])
        register_workspace_dir(ws)   # 不抛
        assert get_workspace_dir("ok2") is ws

    def test_register_accepts_when_required_disabled(self):
        """required_domain_kinds=[] → 跳过校验。"""
        ws = WorkspaceDef(
            name="ok3", display_name="ok3",
            domains=[_mk_domain("only_one")],
            required_domain_kinds=[])
        register_workspace_dir(ws)
        assert get_workspace_dir("ok3") is ws

    def test_extra_business_domains_allowed(self):
        """除了 4 类必备，额外的 business domain 允许。"""
        ws = WorkspaceDef(
            name="ok4", display_name="ok4",
            domains=[
                _mk_domain("organization"),
                _mk_domain("personnel"),
                _mk_domain("category"),
                _mk_domain("identity"),
                _mk_domain("marketing"),   # business
                _mk_domain("finance"),     # business
            ])
        register_workspace_dir(ws)
        assert get_workspace_dir("ok4") is ws

    def test_error_message_lists_missing(self):
        ws = WorkspaceDef(
            name="bad2", display_name="bad2",
            domains=[_mk_domain("organization", kind="organization")],
            required_domain_kinds=["organization", "personnel", "category", "identity"])
        with pytest.raises(ValueError) as excinfo:
            register_workspace_dir(ws)
        msg = str(excinfo.value)
        assert "personnel" in msg
        assert "category" in msg
        assert "identity" in msg


class TestSchemaEnums:

    def test_org_unit_level_values(self):
        """5 级 + 生鲜 Dept 第 6 级。"""
        values = {e.value for e in OrgUnitLevel}
        assert values == {"brand", "org_group", "channel", "region", "store", "dept"}

    def test_category_level_values(self):
        values = {e.value for e in CategoryLevel}
        assert values == {"department", "category_group", "category", "sub_category", "variety"}


class TestRequiredObjectsByKind:

    def test_required_objects_specified(self):
        """设计文档 §3.2/§3.3/§3.4：每类 domain 必含的 Object。"""
        assert REQUIRED_OBJECTS_BY_KIND["organization"] == ["OrgUnit"]
        assert REQUIRED_OBJECTS_BY_KIND["personnel"] == ["Employee"]
        assert REQUIRED_OBJECTS_BY_KIND["category"] == ["Category"]
        assert REQUIRED_OBJECTS_BY_KIND["identity"] == ["User", "Role", "PermissionGrant"]
