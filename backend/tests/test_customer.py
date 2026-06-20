"""测试 CustomerConfig + OrgUnit 树（P1 客户配置）。"""
import os
import pytest
from engine.customer import CustomerConfig, OrgUnit, load_customer_config


def test_customer_config_basic():
    cfg = CustomerConfig(
        customer_id="c1", name="测试客户", source_pack="retail",
        storage_type="json_files", data_dir="/tmp/c1",
        enabled_domains=["marketing"], enabled_processes=["clearance"])
    assert cfg.customer_id == "c1"
    assert cfg.enabled_domains == ["marketing"]


def test_org_unit_tree():
    """OrgUnit 树：parent 链 + 子孙查询。"""
    units = [
        OrgUnit(id="hq", parent=None),
        OrgUnit(id="region_north", parent="hq"),
        OrgUnit(id="store_001", parent="region_north"),
        OrgUnit(id="store_002", parent="region_north"),
    ]
    tree = OrgUnit.Tree(units)
    # store_001 的祖先链
    assert tree.ancestors("store_001") == ["store_001", "region_north", "hq"]
    # region_north 的子孙
    assert set(tree.descendants("region_north")) == {"region_north", "store_001", "store_002"}
    # hq 看全部
    assert set(tree.descendants("hq")) == {"hq", "region_north", "store_001", "store_002"}


def test_org_unit_user_sees_descendants():
    """店长在 store_001 只看 store_001；区域经理在 region_north 看 region_north + 下属店。"""
    units = [
        OrgUnit(id="hq", parent=None),
        OrgUnit(id="region_north", parent="hq"),
        OrgUnit(id="store_001", parent="region_north"),
        OrgUnit(id="store_002", parent="region_north"),
    ]
    tree = OrgUnit.Tree(units)
    assert tree.visible_units("store_001") == {"store_001"}
    assert tree.visible_units("region_north") == {"region_north", "store_001", "store_002"}


def test_load_customer_config_default():
    """加载默认客户配置（data/customers/customer_default/config.yaml）。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.dirname(base)
    cfg = load_customer_config(os.path.join(root, "data", "customers", "customer_default"))
    assert cfg.customer_id == "customer_default"
    assert cfg.storage_type == "json_files"


def test_customer_registry():
    """客户注册表：注册/获取/列表。"""
    from engine.customer import register_customer, get_customer, all_customers, clear_customers
    clear_customers()
    cfg = CustomerConfig(customer_id="cx", name="x", source_pack="retail",
                         storage_type="json_files", data_dir="/tmp")
    register_customer(cfg)
    assert get_customer("cx") is cfg
    assert len(all_customers()) >= 1
    clear_customers()
