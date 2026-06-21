"""测试 TenantContext 值对象（P1 双层租户地基）。"""
import pytest
from engine.tenant import TenantContext


def test_tenant_context_basic():
    tc = TenantContext(workspace_name="customer_001", org_unit_id="store_001")
    assert tc.workspace_name == "customer_001"
    assert tc.org_unit_id == "store_001"


def test_tenant_context_wildcard_org_unit():
    """org_unit_id='*' 表示看该客户所有 OrgUnit 的数据（如总部角色）。"""
    tc = TenantContext(workspace_name="customer_001", org_unit_id="*")
    assert tc.sees_all_org_units() is True


def test_tenant_context_specific_org_unit():
    tc = TenantContext(workspace_name="customer_001", org_unit_id="store_001")
    assert tc.sees_all_org_units() is False


def test_tenant_context_matches_record_same_customer_same_org():
    tc = TenantContext(workspace_name="c1", org_unit_id="store_001")
    record = {"workspace_name": "c1", "org_unit_id": "store_001"}
    assert tc.matches(record) is True


def test_tenant_context_matches_record_wildcard_org():
    """通配 org_unit 看同客户所有记录。"""
    tc = TenantContext(workspace_name="c1", org_unit_id="*")
    record = {"workspace_name": "c1", "org_unit_id": "store_099"}
    assert tc.matches(record) is True


def test_tenant_context_rejects_different_customer():
    tc = TenantContext(workspace_name="c1", org_unit_id="*")
    record = {"workspace_name": "c2", "org_unit_id": "store_001"}
    assert tc.matches(record) is False


def test_tenant_context_rejects_different_org_unit():
    tc = TenantContext(workspace_name="c1", org_unit_id="store_001")
    record = {"workspace_name": "c1", "org_unit_id": "store_002"}
    assert tc.matches(record) is False


def test_tenant_context_default_compat():
    """向后兼容：默认上下文 = customer_default + 通配 org。"""
    tc = TenantContext.default()
    assert tc.workspace_name == "jjy"
    assert tc.sees_all_org_units() is True


def test_tenant_context_matches_legacy_tenant_id_record():
    """旧数据只有 tenant_id 无 customer_id/org_unit_id —— 视为 jjy。"""
    tc = TenantContext.default()
    record = {"tenant_id": "jjy"}  # 旧格式
    assert tc.matches(record) is True


def test_tenant_context_from_dict():
    """从请求上下文字典构造。"""
    tc = TenantContext.from_headers({"X-Customer-ID": "c1", "X-Org-Unit-ID": "store_001"})
    assert tc.workspace_name == "c1"
    assert tc.org_unit_id == "store_001"


def test_tenant_context_from_headers_defaults():
    """缺 header 时默认 jjy + 通配。"""
    tc = TenantContext.from_headers({})
    assert tc.workspace_name == "jjy"
    assert tc.sees_all_org_units() is True
