"""测试 main.py 中间件按 X-Customer-ID/X-Org-Unit-ID 注入（P1）。"""
import os
import pytest
from fastapi.testclient import TestClient


def test_health_no_tenant_headers():
    """/health 不需要 tenant header。"""
    os.environ["QWEN_API_KEY"] = "stub"
    import main
    client = TestClient(main.app)
    r = client.get("/health")
    assert r.status_code == 200


def test_tenant_contextvar_set_from_headers():
    """中间件从 X-Customer-ID/X-Org-Unit-ID 解析，不报错。"""
    os.environ["QWEN_API_KEY"] = "stub"
    import main
    client = TestClient(main.app)
    r = client.get("/health", headers={"X-Customer-ID": "c1", "X-Org-Unit-ID": "store_001"})
    assert r.status_code == 200


def test_tenant_contextvar_defaults():
    """缺 header 时 TenantContext 默认 customer_default + 通配。"""
    from engine.tenant import TenantContext
    tc = TenantContext.from_headers({})
    assert tc.workspace_name == "customer_default"
    assert tc.sees_all_org_units() is True


def test_middleware_uses_customer_headers():
    """中间件读到 X-Customer-ID 并设置 contextvar（通过 /health 间接验不报错）。"""
    os.environ["QWEN_API_KEY"] = "stub"
    import main
    client = TestClient(main.app)
    # 带不同 customer 的请求都应 200（不因未知 customer 报错）
    r1 = client.get("/health", headers={"X-Customer-ID": "customer_001"})
    r2 = client.get("/health", headers={"X-Customer-ID": "customer_002"})
    assert r1.status_code == 200
    assert r2.status_code == 200
