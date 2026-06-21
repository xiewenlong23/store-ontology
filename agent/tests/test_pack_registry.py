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


def test_get_ontology_parser_default_uses_pack():
    """vertical registry 已移除；get_ontology_parser 默认路径走 pack（spec §5.3 决策1）。

    验证默认调用（不传 name）返回带 registry 的对象，且签名不再接受 positional name。
    """
    from engine.parser import get_ontology_parser
    import inspect
    # 方式1（按 name）已删除：vertical 参数应不在签名里
    params = inspect.signature(get_ontology_parser).parameters
    assert "vertical" not in params, "get_ontology_parser 不应再接受 vertical 参数"
    p = get_ontology_parser()  # 默认 pack 路径
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


def test_pack_to_registry_deterministic():
    """pack_to_registry 多次构建结果一致（vertical 缓存已移除，无缓存依赖）。"""
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
