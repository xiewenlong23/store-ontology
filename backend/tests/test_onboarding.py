"""测试 onboarding 工具：ontocopy / ontoseed（P3）。"""
import os
import json
import pytest
from engine.onboarding import copy_pack_to_customer, seed_customer_data


# ============ T1: ontocopy ============

def test_copy_pack_creates_customer_ontology(tmp_path, monkeypatch):
    """copy 行业包到客户目录：生成 ontology/ + config.yaml。"""
    # mock packs/retail 路径指向临时 pack
    pack_dir = tmp_path / "packs" / "retail"
    (pack_dir / "domains" / "marketing").mkdir(parents=True)
    (pack_dir / "domains" / "marketing" / "domain.ttl").write_text(
        '@prefix store: <http://x#> .\n@store:Product a rdfs:Class ;\n'
        '    store:properties "id:string" ; store:storage "products.json" .', encoding="utf-8")
    (pack_dir / "domains" / "marketing" / "actions").mkdir()
    (pack_dir / "domains" / "marketing" / "actions" / "test.yaml").write_text(
        "api_name: test\ntarget_object_type: Product\nedits_object_types: []\n"
        "parameters: []\nside_effects: []\n", encoding="utf-8")
    (pack_dir / "processes" / "clearance" / "actions").mkdir(parents=True)
    (pack_dir / "processes" / "clearance" / "actions" / "submit.yaml").write_text(
        "api_name: submit\ntarget_object_type: Task\nedits_object_types: []\n"
        "parameters: []\nside_effects: []\n", encoding="utf-8")

    customer_dir = tmp_path / "customers" / "customer_test"

    copy_pack_to_customer(
        pack_root=str(pack_dir),
        customer_root=str(customer_dir),
        customer_id="customer_test",
        customer_name="测试客户",
        pack_name="retail")

    # 验证：ontology 目录有 domain TTL + Action
    assert (customer_dir / "ontology" / "domains" / "marketing" / "domain.ttl").exists()
    assert (customer_dir / "ontology" / "domains" / "marketing" / "actions" / "test.yaml").exists()
    assert (customer_dir / "ontology" / "processes" / "clearance" / "actions" / "submit.yaml").exists()
    # config.yaml 存在且有内容
    assert (customer_dir / "config.yaml").exists()
    import yaml
    cfg = yaml.safe_load((customer_dir / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["customer_id"] == "customer_test"
    assert cfg["source_pack"] == "retail"
    assert "marketing" in cfg["enabled_domains"]
    assert "clearance" in cfg["enabled_processes"]
    # data 目录存在
    assert (customer_dir / "data").is_dir()


# ============ T2: ontoseed ============

def test_seed_data_valid(tmp_path):
    """灌入合法数据→写入客户 data 目录。"""
    customer_dir = tmp_path / "customers" / "c1"
    (customer_dir / "data").mkdir(parents=True)
    # mock registry：Product 有 id:string, name:string
    from engine.parser import ObjectType, PropertyDef, EntityRegistry
    reg = EntityRegistry()
    reg.object_types["Product"] = ObjectType(
        id="Product", label="商品", label_zh="商品", comment="",
        properties=[PropertyDef("id", "string"), PropertyDef("name", "string")],
        storage_file="products.json", status="active")

    source = tmp_path / "source.json"
    source.write_text(json.dumps([
        {"id": "p1", "name": "酸奶"},
        {"id": "p2", "name": "牛奶"},
    ]), encoding="utf-8")

    seed_customer_data(
        customer_data_dir=str(customer_dir / "data"),
        source_file=str(source),
        object_type="Product",
        registry=reg)

    out = json.loads((customer_dir / "data" / "products.json").read_text(encoding="utf-8"))
    assert len(out) == 2
    assert out[0]["id"] == "p1"


def test_seed_data_missing_required_field(tmp_path):
    """缺必填字段(id)→报错，不写入。"""
    customer_dir = tmp_path / "customers" / "c2"
    (customer_dir / "data").mkdir(parents=True)
    from engine.parser import ObjectType, PropertyDef, EntityRegistry
    reg = EntityRegistry()
    reg.object_types["Product"] = ObjectType(
        id="Product", label="商品", label_zh="商品", comment="",
        properties=[PropertyDef("id", "string"), PropertyDef("name", "string")],
        storage_file="products.json", status="active")

    source = tmp_path / "bad.json"
    source.write_text(json.dumps([{"name": "无ID商品"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="id"):
        seed_customer_data(
            customer_data_dir=str(customer_dir / "data"),
            source_file=str(source),
            object_type="Product",
            registry=reg)
    # 不应写入文件
    assert not (customer_dir / "data" / "products.json").exists()
