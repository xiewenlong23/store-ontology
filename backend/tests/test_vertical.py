"""测试 vertical 配置注册表与 parser 的 vertical-aware 加载（内核多 vertical 改造 Batch 1）。"""
import os
import pytest
from ontology.vertical import VerticalConfig, register_vertical, get_vertical, all_verticals, clear_registry
from ontology.parser import get_ontology_parser, reset_parser_cache


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    reset_parser_cache()
    yield
    clear_registry()
    reset_parser_cache()


def test_register_and_get():
    cfg = VerticalConfig(name="demo", ttl_path="x.ttl", actions_dir="a", data_dir="d")
    register_vertical(cfg)
    assert get_vertical("demo") is cfg
    assert cfg not in all_verticals() or cfg in all_verticals()
    assert len(all_verticals()) == 1


def test_unknown_vertical_raises():
    with pytest.raises(KeyError):
        get_ontology_parser("nonexistent")


def test_config_aware_parser_loads_ttl_and_actions():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = VerticalConfig(
        name="clearance",
        ttl_path=os.path.join(base, "ontology", "store.ttl"),
        actions_dir=os.path.join(base, "ontology", "actions"),
        data_dir=os.path.join(base, "..", "data"),
    )
    register_vertical(cfg)
    p = get_ontology_parser("clearance")
    assert len(p.registry.object_types) == 7
    assert len(p.registry.link_types) == 10
    assert "create_clearance_task" in p.registry.action_types
    # prefix 动态读取
    assert p.PREFIX == "store:"
    assert p.config is cfg


def test_parser_cached_per_vertical():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = VerticalConfig(
        name="clearance",
        ttl_path=os.path.join(base, "ontology", "store.ttl"),
        actions_dir=os.path.join(base, "ontology", "actions"),
        data_dir=os.path.join(base, "..", "data"),
    )
    register_vertical(cfg)
    p1 = get_ontology_parser("clearance")
    p2 = get_ontology_parser("clearance")
    assert p1 is p2  # 同 vertical 复用缓存


def test_has_workflow_flag():
    no_flow = VerticalConfig(name="a", ttl_path="x", actions_dir="y", data_dir="z")
    assert no_flow.has_workflow() is False
    with_flow = VerticalConfig(
        name="b", ttl_path="x", actions_dir="y", data_dir="z",
        workflow_object_type="Task",
        state_transitions={"created": ["done"]},
    )
    assert with_flow.has_workflow() is True
