"""测试 Repository 双字段过滤（P1：customer_id 硬隔离 + org_unit_id 范围）。"""
import json
import os
from engine.repository import JSONFileRepository
from engine.tenant import TenantContext
from engine.parser import ObjectType, PropertyDef, EntityRegistry


def _registry():
    store = ObjectType(id="Store", label="门店", label_zh="门店", comment="",
                       properties=[PropertyDef(name="id", type="string")],
                       storage_file="stores.json", status="active")
    reg = EntityRegistry()
    reg.object_types = {"Store": store}
    return reg


def _seed(data_dir, rows):
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "stores.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f)


def test_read_filters_by_customer(tmp_path):
    """不同 customer 数据硬隔离。"""
    _seed(str(tmp_path), [
        {"id": "s1", "customer_id": "c1", "org_unit_id": "store_001", "name": "A"},
        {"id": "s2", "customer_id": "c2", "org_unit_id": "store_001", "name": "B"},
    ])
    repo = JSONFileRepository(data_dir=str(tmp_path), registry=_registry())
    tc1 = TenantContext(customer_id="c1", org_unit_id="*")
    tc2 = TenantContext(customer_id="c2", org_unit_id="*")
    assert len(repo.read("Store", tc1)) == 1
    assert repo.read("Store", tc1)[0]["id"] == "s1"
    assert len(repo.read("Store", tc2)) == 1
    assert repo.read("Store", tc2)[0]["id"] == "s2"


def test_read_filters_by_org_unit(tmp_path):
    """同 customer 内按 org_unit 过滤。"""
    _seed(str(tmp_path), [
        {"id": "s1", "customer_id": "c1", "org_unit_id": "store_001", "name": "A"},
        {"id": "s2", "customer_id": "c1", "org_unit_id": "store_002", "name": "B"},
    ])
    repo = JSONFileRepository(data_dir=str(tmp_path), registry=_registry())
    tc = TenantContext(customer_id="c1", org_unit_id="store_001")
    rows = repo.read("Store", tc)
    assert len(rows) == 1
    assert rows[0]["id"] == "s1"


def test_read_wildcard_org_sees_all(tmp_path):
    """通配 org_unit 看同客户所有。"""
    _seed(str(tmp_path), [
        {"id": "s1", "customer_id": "c1", "org_unit_id": "store_001", "name": "A"},
        {"id": "s2", "customer_id": "c1", "org_unit_id": "store_002", "name": "B"},
    ])
    repo = JSONFileRepository(data_dir=str(tmp_path), registry=_registry())
    tc = TenantContext(customer_id="c1", org_unit_id="*")
    assert len(repo.read("Store", tc)) == 2


def test_write_stamps_customer_and_org(tmp_path):
    """写入时盖上 customer_id + org_unit_id。"""
    _seed(str(tmp_path), [])
    repo = JSONFileRepository(data_dir=str(tmp_path), registry=_registry())
    tc = TenantContext(customer_id="c1", org_unit_id="store_001")
    repo.write("Store", tc, {"id": "s_new", "name": "新"}, create=True)
    rows = repo.read("Store", tc)
    assert rows[0]["customer_id"] == "c1"
    assert rows[0]["org_unit_id"] == "store_001"


def test_backward_compat_legacy_tenant_id_string(tmp_path):
    """旧调用传字符串 tenant_id 时兼容（视为 customer_default + 通配）。"""
    _seed(str(tmp_path), [
        {"id": "s1", "tenant_id": "tenant_default", "name": "A"},
    ])
    repo = JSONFileRepository(data_dir=str(tmp_path), registry=_registry())
    # 旧式字符串调用
    rows = repo.read("Store", "tenant_default")
    assert len(rows) == 1  # 旧数据可见
