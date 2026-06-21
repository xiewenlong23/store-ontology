"""测试 bootstrap_customer 升级：从客户 ontology 目录构建（P3-T3）。"""
import os
import json
import pytest
import tempfile
import shutil

from engine.workspace_bootstrap import bootstrap_workspace, reset_instances
from engine.workspace import WorkspaceConfig, register_workspace, clear_workspaces


@pytest.fixture(autouse=True)
def _clean():
    reset_instances()
    clear_workspaces()
    yield
    reset_instances()
    clear_workspaces()


def _make_customer_with_ontology(tmp_path, workspace_name="customer_test"):
    """构造一个有自己 ontology 目录的客户（模拟 ontocopy 后）。"""
    cust_dir = tmp_path / "customers" / workspace_name
    ont_dir = cust_dir / "ontology" / "domains" / "marketing"
    ont_dir.mkdir(parents=True)
    # 简化 TTL：一个 Product
    (ont_dir / "domain.ttl").write_text(
        '@prefix store: <http://x#> .\n'
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n'
        'store:Product a rdfs:Class ;\n'
        '    rdfs:label "商品"@zh , "Product"@en ;\n'
        '    store:properties "id:string,name:string,organic_cert:string" ;\n'
        '    store:storage "products.json" .\n', encoding="utf-8")
    # data
    (cust_dir / "data").mkdir(parents=True)
    (cust_dir / "data" / "products.json").write_text(
        json.dumps([{"id": "p1", "name": "有机酸奶", "organic_cert": "USDA",
                     "workspace_name": "customer_test"}]),
        encoding="utf-8")
    return str(cust_dir)


def test_bootstrap_uses_customer_ontology(tmp_path):
    """有客户 ontology 目录时，registry 来自客户自定义 TTL（非全局 store.ttl）。"""
    cust_dir = _make_customer_with_ontology(tmp_path)
    cfg = WorkspaceConfig(
        workspace_name="customer_test", name="测试",
        storage_type="json_files", data_dir=os.path.join(cust_dir, "data"))
    register_workspace(cfg)

    inst = bootstrap_workspace("customer_test")
    # 客户自定义的 Product 有 organic_cert 属性（全局 store.ttl 没有）
    product = inst.registry.object_types.get("Product")
    assert product is not None
    prop_names = {p.name for p in product.properties}
    assert "organic_cert" in prop_names  # 客户自定义字段


def test_bootstrap_reads_customer_data(tmp_path):
    """客户 agent 实例能读该客户的数据目录。"""
    cust_dir = _make_customer_with_ontology(tmp_path)
    cfg = WorkspaceConfig(
        workspace_name="customer_test", name="测试",
        storage_type="json_files", data_dir=os.path.join(cust_dir, "data"))
    register_workspace(cfg)

    inst = bootstrap_workspace("customer_test")
    rows = inst.repository.read("Product", inst.tenant_context)
    assert len(rows) == 1
    assert rows[0]["name"] == "有机酸奶"


def test_bootstrap_fallback_no_ontology(tmp_path):
    """无客户 ontology 目录时回退全局 store.ttl（customer_default 兼容）。"""
    inst = bootstrap_workspace("jjy")
    assert inst is not None
    # 全局 store.ttl 的 Product 无 organic_cert
    product = inst.registry.object_types.get("Product")
    prop_names = {p.name for p in product.properties}
    assert "organic_cert" not in prop_names


def test_bootstrap_instance_isolated_per_customer(tmp_path):
    """两个客户的 registry 独立（本体语义隔离）。"""
    d1 = _make_customer_with_ontology(tmp_path, "ca")
    d2 = _make_customer_with_ontology(tmp_path, "cb")
    # cb 的 Product 加一个额外字段
    (os.path.join(d2, "ontology", "domains", "marketing", "domain.ttl"))
    register_workspace(WorkspaceConfig(workspace_name="ca", name="A",
        data_dir=os.path.join(d1, "data")))
    register_workspace(WorkspaceConfig(workspace_name="cb", name="B",
        data_dir=os.path.join(d2, "data")))

    ia = bootstrap_workspace("ca")
    ib = bootstrap_workspace("cb")
    assert ia.registry is not ib.registry
    assert ia.repository is not ib.repository
