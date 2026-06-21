"""测试 pack 注册表（行业包装配模型，spec §5.3）。

原 test_vertical.py 迁移而来：vertical registry 已移除，本文件测 IndustryPack 装配。
"""
import os
import pytest
from engine.pack import (IndustryPack, CapabilityDomain, ValueChainProcess,
                          register_pack, get_pack, all_packs, clear_packs, pack_to_registry)


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
    """vertical registry 已移除；get_ontology_parser 不再接受 name（spec §5.3 决策1）。

    按显式 ttl_path 调用是合法的；此处验证旧 name 调用方式已无意义，
    改为验证 get_ontology_parser 的默认路径（pack）可工作。
    """
    from engine.parser import get_ontology_parser
    p = get_ontology_parser()  # 默认 pack 路径，不传 name
    assert p is not None
    assert hasattr(p, "registry")


def test_config_aware_parser_loads_ttl_and_actions():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = IndustryPack(
        name="test_pack", display_name="测试",
        domains=[CapabilityDomain(
            name="marketing", display_name="营销",
            ttl_path=os.path.join(base, "..", "workspace", "retail", "ontology", "domains", "marketing", "domain.ttl"),
            actions_dir=os.path.join(base, "..", "workspace", "retail", "ontology", "domains", "marketing", "actions"))])
    register_pack(cfg)
    p = pack_to_registry(cfg)
    assert len(p.object_types) >= 2  # Product + NearExpiryProduct
    assert "create_clearance_task" in p.action_types


def test_parser_cached_per_vertical():
    """vertical 缓存已移除；验证 pack_to_registry 多次构建结果一致（无缓存依赖）。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = IndustryPack(
        name="test_pack", display_name="测试",
        domains=[CapabilityDomain(
            name="marketing", display_name="营销",
            ttl_path=os.path.join(base, "..", "workspace", "retail", "ontology", "domains", "marketing", "domain.ttl"),
            actions_dir=os.path.join(base, "..", "workspace", "retail", "ontology", "domains", "marketing", "actions"))])
    register_pack(cfg)
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
