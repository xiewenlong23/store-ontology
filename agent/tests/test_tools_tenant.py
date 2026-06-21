"""测试工具层按 customer/org_unit 过滤（P1）。"""
from agent.tools import query_entity
import agent.tools.shared as T


def _setup(monkeypatch, data_dir):
    from tests._clearance_helper import build_clearance_executor, build_clearance_registry
    ex, repo = build_clearance_executor(data_dir)
    reg = repo.registry
    from engine.parser import OntologyParser
    monkeypatch.setattr(T, "_parser", lambda vertical=None: type('P',(),{'registry':reg})())
    monkeypatch.setattr(T, "_get_repo", lambda tenant=None, vertical=None: repo)
    monkeypatch.setattr(T, "_get_executor", lambda vertical=None: ex)


def test_query_entity_accepts_customer_and_org_unit(clearance_data_dir, monkeypatch):
    """工具接受 workspace_name + org_unit_id，按 workspace 过滤。"""
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({
        "entity_type": "Store",
        "workspace_name": "jjy",
        "org_unit_id": "*",
    })
    assert "store_001" in out


def test_query_entity_defaults_to_customer_default(clearance_data_dir, monkeypatch):
    """不传 customer_id 时默认 jjy。"""
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({"entity_type": "Store"})
    assert "store_001" in out  # 旧数据（无 workspace_name）兼容可见


def test_query_entity_isolates_by_customer(clearance_data_dir, monkeypatch):
    """不同 workspace_name 看不到彼此数据。"""
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({
        "entity_type": "Store",
        "workspace_name": "customer_other",
    })
    assert "store_001" not in out  # 属于 jjy，不属于 customer_other


def test_query_entity_isolates_by_contextvar(clearance_data_dir, monkeypatch):
    """v2-tenant：contextvar 设不同 workspace → 工具返回数据不同（端到端隔离）。

    模拟请求链路：middleware 设 tenant_ctx contextvar → 工具 _tc_ctx() 读它 →
    Repository 按 workspace_name 过滤。不显式传工具参数（依赖 contextvar）。
    """
    _setup(monkeypatch, clearance_data_dir)
    import main
    from engine.tenant import TenantContext

    # contextvar = customer_default → 看得到 store_001
    token = main.tenant_ctx.set(TenantContext(workspace_name="jjy", org_unit_id="*"))
    try:
        out_default = query_entity.invoke({"entity_type": "Store"})
        assert "store_001" in out_default
    finally:
        main.tenant_ctx.reset(token)

    # contextvar = customer_other → 看不到 store_001
    token = main.tenant_ctx.set(TenantContext(workspace_name="customer_other", org_unit_id="*"))
    try:
        out_other = query_entity.invoke({"entity_type": "Store"})
        assert "store_001" not in out_other
    finally:
        main.tenant_ctx.reset(token)
