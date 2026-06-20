"""端到端 onboarding 集成测试（P3-T4）。

完整五步：ontocopy(retail→customer) → 不改 → ontoseed 灌数据 → bootstrap_customer → 验证可用。
"""
import os
import json
import pytest

from engine.onboarding import copy_pack_to_customer, seed_customer_data
from engine.customer import CustomerConfig, register_customer, clear_customers
from engine.customer_bootstrap import bootstrap_customer, reset_instances
from engine.parser import OntologyParser, EntityRegistry
from engine.action_loader import load_actions


@pytest.fixture(autouse=True)
def _clean():
    reset_instances()
    clear_customers()
    yield
    reset_instances()
    clear_customers()


def test_full_onboarding_flow(tmp_path):
    """完整 onboarding：copy → seed → bootstrap → agent 可用。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack_root = os.path.join(base, "packs", "retail")
    customer_root = str(tmp_path / "customers" / "customer_e2e")

    # 步骤①: ontocopy
    copy_pack_to_customer(
        pack_root=pack_root, customer_root=customer_root,
        customer_id="customer_e2e", customer_name="E2E测试客户",
        pack_name="retail")
    assert os.path.exists(os.path.join(customer_root, "ontology", "domains"))

    # 步骤②: 客户不改本体（跳过）

    # 步骤③: ontoseed 灌数据
    # 先构建一个 registry 供 seed 校验（从客户 copy 后的 ontology）
    from engine.customer_bootstrap import _build_registry_from_customer_ontology
    reg = _build_registry_from_customer_ontology(
        os.path.join(customer_root, "ontology"),
        os.path.join(customer_root, "data"))
    assert "Product" in reg.object_types  # copy 成功，能解析

    source = tmp_path / "products_source.json"
    source.write_text(json.dumps([
        {"id": "prod_e2e_1", "name": "测试酸奶", "customer_id": "customer_e2e"},
    ]), encoding="utf-8")
    seed_customer_data(
        customer_data_dir=os.path.join(customer_root, "data"),
        source_file=str(source),
        object_type="Product",
        registry=reg,
        customer_id="customer_e2e")

    # 步骤④: config 已由 ontocopy 生成（data_dir 指向 data/）
    # 步骤⑤: bootstrap_customer
    register_customer(CustomerConfig(
        customer_id="customer_e2e", name="E2E测试客户",
        data_dir=os.path.join(customer_root, "data")))
    inst = bootstrap_customer("customer_e2e")

    # 验证：agent 实例能读客户数据
    rows = inst.repository.read("Product", inst.tenant_context)
    assert len(rows) == 1
    assert rows[0]["name"] == "测试酸奶"

    # 验证：registry 来自客户 ontology（7 个 clearance Object）
    assert "NearExpiryProduct" in inst.registry.object_types
    assert "Task" in inst.registry.object_types
    assert "LossReport" in inst.registry.object_types

    # 验证：客户有 Action
    assert "create_clearance_task" in inst.registry.action_types


def test_two_customers_onboarded_isolated(tmp_path):
    """两个客户各自 onboard，数据 + 本体语义隔离。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack_root = os.path.join(base, "packs", "retail")

    # 客户 A
    root_a = str(tmp_path / "ca")
    copy_pack_to_customer(pack_root, root_a, "ca", "客户A", "retail")
    # 客户 A 改本体：Product 加 custom_field_a
    ttl_a = os.path.join(root_a, "ontology", "domains", "marketing", "domain.ttl")
    content = open(ttl_a, encoding="utf-8").read()
    content = content.replace(
        "cost_price:float,retail_price:float",
        "cost_price:float,retail_price:float,custom_field_a:string")
    open(ttl_a, "w", encoding="utf-8").write(content)
    register_customer(CustomerConfig(customer_id="ca", name="A",
        data_dir=os.path.join(root_a, "data")))
    inst_a = bootstrap_customer("ca")
    props_a = {p.name for p in inst_a.registry.object_types["Product"].properties}
    assert "custom_field_a" in props_a

    # 客户 B（不改）
    root_b = str(tmp_path / "cb")
    copy_pack_to_customer(pack_root, root_b, "cb", "客户B", "retail")
    register_customer(CustomerConfig(customer_id="cb", name="B",
        data_dir=os.path.join(root_b, "data")))
    inst_b = bootstrap_customer("cb")
    props_b = {p.name for p in inst_b.registry.object_types["Product"].properties}
    assert "custom_field_a" not in props_b  # B 没有客户 A 的自定义字段

    # 本体语义隔离
    assert inst_a.registry is not inst_b.registry
