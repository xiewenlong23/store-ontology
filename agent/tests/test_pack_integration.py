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
    """domains_to_registry 合并后含 retail 的 7 个业务 Object + identity domain 的 4 个。"""
    from engine.bootstrap import bootstrap
    from engine.pack import get_workspace_dir, domains_to_registry
    bootstrap()
    ws = get_workspace_dir("retail")
    reg = domains_to_registry(ws, data_dir="../data")
    # 业务 7 Object（marketing/organization/finance）
    business = {"Product", "NearExpiryProduct", "Region", "Store", "Employee", "Task", "LossReport"}
    assert business.issubset(set(reg.object_types))
    # identity domain 4 Object（WP1 新增）
    identity = {"User", "Role", "PermissionGrant", "Session"}
    assert identity.issubset(set(reg.object_types))
