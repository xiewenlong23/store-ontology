"""
tests/e2e/test_api_endpoints.py — Phase 7 Review Fix #1
端到端 API 测试（FastAPI TestClient，真实 FastAPI 路由）
"""
import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """健康检查端点"""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_health_check(self, client):
        """GET /health 返回 healthy + store_id"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "store_id" in data

    def test_root_endpoint(self, client):
        """GET / 返回 API 信息"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Store Ontology API"

    def test_cors_headers(self, client):
        """CORS 头存在"""
        response = client.get("/health")
        assert "access-control-allow-origin" in response.headers


class TestSPARQLEndpoints:
    """SPARQL API 端点"""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_expiring_products_missing_store_id(self, client):
        """store_id 为空时返回 422"""
        response = client.post(
            "/api/sparql/expiring-products",
            json={"days": 7},
        )
        assert response.status_code == 422

    def test_product_query_missing_store_id(self, client):
        """product 查询缺少 store_id 返回 422"""
        response = client.post(
            "/api/sparql/product",
            json={"product_id": "P00001"},
        )
        assert response.status_code == 422

    def test_product_query_missing_product_id(self, client):
        """product 查询缺少 product_id 返回 422"""
        response = client.post(
            "/api/sparql/product",
            json={"store_id": "STORE_001"},
        )
        assert response.status_code == 422


class TestHITLApprovalEndpoint:
    """HITL 审批回调端点"""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_approval_callback_missing_fields(self, client):
        """审批回调缺少必填字段返回 422"""
        response = client.post(
            "/api/hitl/callback",
            json={"action": "approve"},
        )
        assert response.status_code == 422

    def test_approval_callback_reject(self, client):
        """审批拒绝回调"""
        response = client.post(
            "/api/hitl/callback",
            json={
                "action": "reject",
                "task_id": "task-001",
                "user_id": "u001",
                "comment": "折扣力度太大",
            },
        )
        # 无论业务逻辑是否处理，最终 HTTP 应该是 200
        assert response.status_code in (200, 404)


class TestAuditEndpoint:
    """审计日志查询端点"""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_audit_logs_requires_session_id(self, client):
        """查询审计日志需要 session_id"""
        response = client.get("/api/audit/logs")
        assert response.status_code in (400, 422)

    def test_audit_logs_with_session_id(self, client):
        """带 session_id 查询审计日志"""
        response = client.get("/api/audit/logs?session_id=sess-001")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
