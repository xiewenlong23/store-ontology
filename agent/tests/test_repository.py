import json
from engine.repository import JSONFileRepository
from engine.parser import ObjectType, PropertyDef, EntityRegistry
from engine.errors import ActionRequiredError


def _registry_with(managed: bool):
    """构造一个最小 registry：Store（managed 可控）+ 一个自由类型 Region。"""
    store = ObjectType(
        id="Store", label="门店", label_zh="门店", comment="",
        properties=[PropertyDef(name="id", type="string")],
        storage_file="stores.json", status="active",
        edits_only_via_actions=managed,
    )
    reg = EntityRegistry()
    reg.object_types = {"Store": store}
    return reg


def test_read_filters_by_tenant(tmp_data_dir):
    reg = _registry_with(managed=False)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    rows = repo.read("Store", "tenant_default")
    assert len(rows) == 1
    assert rows[0]["id"] == "store_001"


def test_read_one_missing_returns_none(tmp_data_dir):
    reg = _registry_with(managed=False)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    assert repo.read_one("Store", "tenant_default", "nope") is None


def test_write_stamps_tenant(tmp_data_dir):
    reg = _registry_with(managed=False)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    from engine.tenant import TenantContext
    tc = TenantContext(workspace_name="customer_default", org_unit_id="*")
    repo.write("Store", tc,
               {"id": "store_002", "name": "新店"}, create=True)
    rec = repo.read_one("Store", tc, "store_002")
    assert rec["workspace_name"] == "customer_default"
    assert rec["org_unit_id"] == "*"


def test_write_blocked_when_edits_only(tmp_data_dir):
    reg = _registry_with(managed=True)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    try:
        repo.write("Store", "tenant_default", {"id": "store_002"}, create=True)
        assert False, "应抛 ActionRequiredError"
    except ActionRequiredError:
        pass


def test_write_bypass_for_executor(tmp_data_dir):
    reg = _registry_with(managed=True)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    repo.write("Store", "tenant_default", {"id": "store_002"}, create=True,
               bypass_action_check=True)
    assert repo.read_one("Store", "tenant_default", "store_002") is not None


def test_tenant_isolation(tmp_data_dir):
    reg = _registry_with(managed=False)
    repo = JSONFileRepository(data_dir=tmp_data_dir, registry=reg)
    from engine.tenant import TenantContext
    tc_a = TenantContext(workspace_name="customer_a", org_unit_id="*")
    tc_b = TenantContext(workspace_name="customer_b", org_unit_id="*")
    repo.write("Store", tc_b, {"id": "store_002"}, create=True)
    # 默认数据（无 customer_id）属于 customer_default，不属 a/b
    assert len(repo.read("Store", tc_a)) == 0
    assert len(repo.read("Store", tc_b)) == 1
