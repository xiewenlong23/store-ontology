"""
tests/integration/test_agent_flow.py — Phase 7 Review Fix #1
完整折扣流程集成测试（Mock 所有外部依赖）
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


class TestDiscountHITLFlow:
    """折扣 → HITL → 审批完整流程集成测试"""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    @patch("app.agent.tools.sparql_tools._sparql_query")
    @patch("app.agent.tools.discount_tools.write_audit_log")
    @patch("app.integrations.feishu_notifier.send_discount_approval_card")
    def test_discount_flow_clerk_triggers_hitl(
        self,
        mock_card,
        mock_audit,
        mock_sparql,
        client,
    ):
        """
        场景：店员发起折扣 → 触发 HITL 审批
        验证：interrupt=True / task_id 不为空
        """
        mock_sparql.return_value = {
            "results": {
                "bindings": [
                    {
                        "expiry_date": {"value": "2025-05-20"},
                        "current_stock": {"value": "50"},
                    }
                ]
            }
        }
        mock_card.return_value = {"code": 0, "data": {"message_id": "msg-123"}}

        response = client.post(
            "/api/copilotkit",
            json={
                "message": "这批牛奶还有5天过期，打8折处理",
                "properties": {
                    "store_id": "STORE_001",
                    "user_id": "u001",
                    "role": "clerk",
                    "session_id": "sess-test",
                },
            },
        )

        assert response.status_code == 200
        result = response.json()

        # HITL 中断触发
        assert result.get("interrupt") is True or "task_id" in result
        # 有审计日志写入
        mock_audit.assert_called()

    @patch("app.agent.tools.sparql_tools._sparql_query")
    @patch("app.agent.tools.discount_tools.write_audit_log")
    def test_discount_store_manager_no_hitl(
        self,
        mock_audit,
        mock_sparql,
        client,
    ):
        """
        场景：店长发起 ≤70% 折扣 → 无需审批，直接执行
        验证：不触发 HITL 中断
        """
        mock_sparql.return_value = {
            "results": {
                "bindings": [
                    {
                        "expiry_date": {"value": "2025-06-01"},
                        "current_stock": {"value": "50"},
                    }
                ]
            }
        }

        response = client.post(
            "/api/copilotkit",
            json={
                "message": "临期牛奶8折处理",
                "properties": {
                    "store_id": "STORE_001",
                    "user_id": "u002",
                    "role": "store_manager",
                    "session_id": "sess-test",
                },
            },
        )

        assert response.status_code == 200
        result = response.json()
        # 店长 ≤70% 直接通过，不中断
        assert result.get("interrupt") is not True


class TestSPARQLQueryIntegration:
    """SPARQL 查询集成测试"""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    @patch("app.agent.tools.sparql_tools._sparql_query")
    def test_query_expiring_products(self, mock_sparql, client):
        """临期商品查询"""
        mock_sparql.return_value = {
            "results": {
                "bindings": [
                    {
                        "product_id": {"value": "P00001"},
                        "product_name": {"value": "伊利纯牛奶250ml"},
                        "remaining_days": {"value": "3"},
                        "shelf_date": {"value": "2025-05-15"},
                    },
                    {
                        "product_id": {"value": "P00002"},
                        "product_name": {"value": "蒙牛特仑苏"},
                        "remaining_days": {"value": "7"},
                        "shelf_date": {"value": "2025-05-19"},
                    },
                ]
            }
        }

        response = client.post(
            "/api/sparql/expiring-products",
            json={"store_id": "STORE_001", "days": 7},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["count"] == 2
        assert len(result["products"]) == 2

    @patch("app.agent.tools.sparql_tools._sparql_query")
    def test_query_product_info(self, mock_sparql, client):
        """商品信息查询"""
        mock_sparql.return_value = {
            "results": {
                "bindings": [
                    {
                        "name": {"value": "伊利纯牛奶250ml"},
                        "category": {"value": "乳制品"},
                        "retail_price": {"value": "59.00"},
                        "cost_price": {"value": "45.60"},
                        "supplier": {"value": "伊利集团华东分公司"},
                    }
                ]
            }
        }

        response = client.post(
            "/api/sparql/product",
            json={"product_id": "P00001", "store_id": "STORE_001"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["name"] == "伊利纯牛奶250ml"
        assert result["category"] == "乳制品"


class TestMCPIntegration:
    """MCP 工具集成测试（Mock langchain-mcp-adapters）"""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    @patch("app.agent.tools.mcp_tools.MultiServerMCPClient")
    def test_mcp_client_initializes(self, mock_client_class, client):
        """MCP 客户端初始化成功"""
        mock_instance = AsyncMock()
        mock_instance.get_tools.return_value = []
        mock_client_class.return_value = mock_instance

        from app.agent.tools.mcp_tools import init_mcp_clients, _reset_mcp
        _reset_mcp()

        result = init_mcp_clients()
        assert isinstance(result, list)

    @patch("app.agent.tools.mcp_tools.MultiServerMCPClient")
    def test_mcp_client_graceful_failure(self, mock_client_class, client):
        """MCP 客户端初始化失败时优雅降级"""
        mock_client_class.side_effect = RuntimeError("Connection refused")

        from app.agent.tools.mcp_tools import init_mcp_clients, _reset_mcp
        _reset_mcp()

        result = init_mcp_clients()
        assert result == []  # 降级为空列表
