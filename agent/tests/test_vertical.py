"""测试 pack 注册表（原 vertical 测试迁移为 pack 测试）。"""
import os
import pytest
from engine.vertical import VerticalConfig  # 类仍保留（ValueChainProcess 的兼容基类）
from engine.pack import (IndustryPack, CapabilityDomain, ValueChainProcess,
                          register_pack, get_pack, all_packs, clear_packs)


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_packs()
    yield
    clear_packs()


def test_register_and_get():
    pack = IndustryPack(name="demo", display_name="测试")
    register_pack(pack)
    assert get_pack("demo") is pack
    assert len(all_packs()) == 1


def test_unknown_vertical_raises():
    from engine.parser import get_ontology_parser, reset_parser_cache
    reset_parser_cache()
    with pytest.raises(KeyError):
        get_ontology_parser("nonexistent")


def test_config_aware_parser_loads_ttl_and_actions():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = IndustryPack(
        name="test_pack", display_name="测试",
        domains=[CapabilityDomain(
            name="marketing", display_name="营销",
            ttl_path=os.path.join(base, "..", "workspace", "retail", "ontology", "domains", "marketing", "domain.ttl"),
            actions_dir=os.path.join(base, "..", "workspace", "retail", "ontology", "domains", "marketing", "actions"))])
    register_pack(cfg)
    from engine.pack import pack_to_registry
    p = pack_to_registry(cfg)
    assert len(p.object_types) >= 2  # Product + NearExpiryProduct
    assert "create_clearance_task" in p.action_types


def test_parser_cached_per_vertical():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = IndustryPack(
        name="test_pack", display_name="测试",
        domains=[CapabilityDomain(
            name="marketing", display_name="营销",
            ttl_path=os.path.join(base, "..", "workspace", "retail", "ontology", "domains", "marketing", "domain.ttl"),
            actions_dir=os.path.join(base, "..", "workspace", "retail", "ontology", "domains", "marketing", "actions"))])
    register_pack(cfg)
    from engine.pack import pack_to_registry
    p1 = pack_to_registry(cfg)
    p2 = pack_to_registry(cfg)
    assert len(p1.object_types) == len(p2.object_types)


def test_has_workflow_flag():
    no_flow = ValueChainProcess(name="a", display_name="x", workflow_object_type="Task")
    assert no_flow.state_transitions == {}
    with_flow = ValueChainProcess(
        name="b", display_name="y", workflow_object_type="Task",
        state_transitions={"created": ["done"]})
    assert with_flow.state_transitions == {"created": ["done"]}
