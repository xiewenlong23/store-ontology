"""测试三级结构 WorkspaceDef/CapabilityDomain/ValueChainProcess（P2）。"""
import pytest
from engine.pack import (
    WorkspaceDef, CapabilityDomain, ValueChainProcess,
    register_workspace_dir, get_workspace_dir, all_workspace_dirs, clear_workspace_dirs, domains_to_registry,
)


def test_capability_domain_basic():
    d = CapabilityDomain(name="marketing", display_name="营销域",
                         ttl_path="/tmp/m.ttl", actions_dir="/tmp/m/actions")
    assert d.name == "marketing"
    assert d.display_name == "营销域"


def test_value_chain_process_basic():
    p = ValueChainProcess(name="clearance", display_name="出清",
                          workflow_object_type="Task")
    assert p.name == "clearance"
    assert p.workflow_object_type == "Task"
    assert p.state_transitions == {}


def test_industry_pack_aggregates():
    d = CapabilityDomain(name="marketing", display_name="营销",
                         ttl_path="/tmp/m.ttl", actions_dir="/tmp/m/a")
    p = ValueChainProcess(name="clearance", display_name="出清",
                          workflow_object_type="Task")
    ws = WorkspaceDef(name="retail", display_name="零售行业包",
                        domains=[d], processes=[p])
    assert len(ws.domains) == 1
    assert len(ws.processes) == 1
    assert ws.domains[0].name == "marketing"
    assert ws.processes[0].name == "clearance"


def test_ws_registry():
    clear_workspace_dirs()
    ws = WorkspaceDef(name="retail", display_name="零售")
    register_workspace_dir(ws)
    assert get_workspace_dir("retail") is ws
    assert len(all_workspace_dirs()) == 1
    clear_workspace_dirs()


def test_ws_to_registry_merges_domains(tmp_path):
    """domains_to_registry 合并 pack 下所有 domain 的 TTL + action。"""
    import os
    # 构造两个域，各一个 TTL + 一个 action（格式对齐 parser：用 rdfs: prefix + 行尾 ' .'）
    d1_dir = tmp_path / "marketing"
    d1_dir.mkdir()
    (d1_dir / "domain.ttl").write_text(
        '@prefix m: <http://x#> .\n'
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n'
        'm:Product a rdfs:Class ;\n'
        '    rdfs:label "商品"@zh , "Product"@en ;\n'
        '    m:properties "id:string,name:string" ;\n'
        '    m:storage "products.json" .\n', encoding="utf-8")
    a1_dir = d1_dir / "actions"
    a1_dir.mkdir()
    (a1_dir / "test_action.yaml").write_text(
        'api_name: test_action\ndisplay_name: 测试\ntarget_object_type: Product\n'
        'edits_object_types: [Product]\nparameters: []\nside_effects: []\n',
        encoding="utf-8")

    d2_dir = tmp_path / "organization"
    d2_dir.mkdir()
    (d2_dir / "domain.ttl").write_text(
        '@prefix o: <http://x#> .\n'
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n'
        'o:Store a rdfs:Class ;\n'
        '    rdfs:label "门店"@zh , "Store"@en ;\n'
        '    o:properties "id:string,name:string" ;\n'
        '    o:storage "stores.json" .\n', encoding="utf-8")

    d1 = CapabilityDomain(name="marketing", display_name="营销",
                          ttl_path=str(d1_dir / "domain.ttl"),
                          actions_dir=str(a1_dir))
    d2 = CapabilityDomain(name="organization", display_name="组织",
                          ttl_path=str(d2_dir / "domain.ttl"),
                          actions_dir=str(d2_dir / "actions"))  # 无 action
    ws = WorkspaceDef(name="retail", display_name="零售", domains=[d1, d2])

    registry = domains_to_registry(ws)
    assert "Product" in registry.object_types
    assert "Store" in registry.object_types
    assert "test_action" in registry.action_types
