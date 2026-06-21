"""测试 bootstrap 发现 + main 聚合逻辑（pack 架构）。"""
import importlib
import pytest

from engine import bootstrap as bootstrap_mod
from engine.pack import all_packs, clear_packs, register_pack, IndustryPack, CapabilityDomain


def test_bootstrap_registers_equipment_repair():
    bootstrap_mod.bootstrap()
    names = [p.name for p in all_packs()]
    assert "equipment_repair" in names


def test_bootstrap_registers_retail():
    bootstrap_mod.bootstrap()
    names = [p.name for p in all_packs()]
    assert "retail" in names


def test_bootstrap_is_idempotent():
    bootstrap_mod.bootstrap()
    n1 = len(all_packs())
    bootstrap_mod.bootstrap()
    n2 = len(all_packs())
    assert n1 == n2


def test_aggregate_pack_tools_loads_query_near_expiry():
    """query_near_expiry 来自 pack process tools。"""
    bootstrap_mod.bootstrap()
    main_mod = importlib.import_module("main")
    tools = main_mod._aggregate_pack_tools()
    names = [getattr(t, "name", "") for t in tools]
    assert "query_near_expiry" in names


def test_aggregate_skill_paths_filters_non_skill_dirs(tmp_path):
    """skills_dir 下无 SKILL.md 的目录应被过滤。"""
    skills = tmp_path / "skills"
    real = skills / "real-skill"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("---\nname: real-skill\n---\n# x\n", encoding="utf-8")
    (skills / "tmp").mkdir()
    (skills / "__pycache__").mkdir()

    # 构造临时 pack 注册 skills_dir
    from engine.pack import ValueChainProcess
    proc = ValueChainProcess(name="t_proc", display_name="t",
                             workflow_object_type="X",
                             skills_dir=str(skills))
    pack = IndustryPack(name="t_pack", display_name="t", processes=[proc])
    register_pack(pack)
    try:
        main_mod = importlib.import_module("main")
        paths = main_mod._aggregate_skill_paths()
        assert "/real-skill/" in paths
        assert "/tmp/" not in paths
        assert "/__pycache__/" not in paths
    finally:
        from engine.pack import _packs
        _packs.pop("t_pack", None)


def test_build_combined_prompt_includes_packs():
    bootstrap_mod.bootstrap()
    main_mod = importlib.import_module("main")
    prompt = main_mod._build_combined_prompt()
    assert "可用实体" in prompt
