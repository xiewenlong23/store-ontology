"""测试 vertical 注册表 bootstrap 与 main 聚合逻辑（内核多 vertical 改造 Batch 3）。"""
import importlib

import pytest

from engine.vertical import clear_registry, all_verticals, register_vertical
from engine.vertical import VerticalConfig
from engine import bootstrap as bootstrap_mod

# 注意：本测试文件不使用 clear_registry autouse fixture。
# main 模块级聚合函数读全局注册表，跨测试清空会导致 flaky。
# 需要隔离的测试自己 register/clear。bootstrap 测试依赖 clearance 已注册的真实状态。


def test_bootstrap_registers_equipment_repair():
    bootstrap_mod.bootstrap()
    names = [c.name for c in all_verticals()]
    assert "equipment_repair" in names


def test_bootstrap_is_idempotent():
    bootstrap_mod.bootstrap()
    n1 = len(all_verticals())
    bootstrap_mod.bootstrap()
    n2 = len(all_verticals())
    assert n1 == n2  # 重复调用不重复注册


def test_aggregate_pack_tools_loads_query_near_expiry():
    """query_near_expiry 现在来自 pack（P2+I-4），不是 vertical。"""
    bootstrap_mod.bootstrap()
    main_mod = importlib.import_module("main")
    # pack 聚合
    tools = main_mod._aggregate_pack_tools()
    names = [getattr(t, "name", "") for t in tools]
    assert "query_near_expiry" in names


def test_aggregate_skill_paths_filters_non_skill_dirs(tmp_path):
    """skills_dir 下无 SKILL.md 的目录（如 tmp/）应被过滤。

    本测试构造一个临时 vertical 配置，与全局 clearance 共存——聚合函数会
    把两者的 skill 路径都收进来，故断言"包含 real-skill"而非"等于"。
    """
    skills = tmp_path / "skills"
    real = skills / "real-skill"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("---\nname: real-skill\n---\n# x\n", encoding="utf-8")
    (skills / "tmp").mkdir()
    (skills / "__pycache__").mkdir()
    cfg = VerticalConfig(
        name="t_test", ttl_path="x", actions_dir="y", data_dir="z", skills_dir=str(skills))
    register_vertical(cfg)
    try:
        main_mod = importlib.import_module("main")
        paths = main_mod._aggregate_skill_paths()
        assert "/real-skill/" in paths
        assert "/tmp/" not in paths
        assert "/__pycache__/" not in paths
    finally:
        from engine.vertical import _registry
        _registry.pop("t_test", None)


def test_build_combined_prompt_includes_packs():
    bootstrap_mod.bootstrap()
    main_mod = importlib.import_module("main")
    prompt = main_mod._build_combined_prompt()
    assert "可用实体" in prompt  # pack/vertical prompt has this
