"""测试工作目录注册 + registry 装配（集成）。"""
import pytest


def test_retail_pack_registered_after_bootstrap():
    from engine.bootstrap import bootstrap
    from engine.pack import get_workspace_dir
    bootstrap()
    assert get_workspace_dir("retail") is not None


def test_clearance_process_has_tools():
    """clearance process 的 tools_module 能 import 且有 TOOLS。"""
    from engine.bootstrap import bootstrap
    from engine.pack import get_workspace_dir
    bootstrap()
    ws = get_workspace_dir("retail")
    clearance = next(p for p in ws.processes if p.name == "clearance")
    import importlib
    mod = importlib.import_module(clearance.tools_module)
    assert hasattr(mod, "TOOLS")
    assert len(mod.TOOLS) >= 1


def test_ws_to_registry_all_objects():
    """domains_to_registry 合并后含全部 7 Object。"""
    from engine.bootstrap import bootstrap
    from engine.pack import get_workspace_dir, domains_to_registry
    bootstrap()
    ws = get_workspace_dir("retail")
    reg = domains_to_registry(ws, data_dir="../data")
    assert len(reg.object_types) == 7
