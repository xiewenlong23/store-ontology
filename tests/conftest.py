"""
Pytest configuration and fixtures for Store Ontology tests.
Phase 7 Review Fix #3 — 修复 pytest_plugins 写法
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock


# ============================================================
# pytest-asyncio 模式配置（推荐写法）
# ============================================================
pytest.mark.asyncio = pytest_asyncio.fixture


@pytest.fixture
def mock_settings():
    """测试用 Settings"""
    from app.config import Settings
    return Settings(
        store_id="TEST_STORE",
        sparql_endpoint="http://localhost:7200",
        database_url="postgresql://test:test@localhost:5432/test",
        feishu_bot_token="test-token",
        feishu_app_id="test-app-id",
        feishu_app_secret="test-secret",
        langsmith_api_key="",
        langsmith_project="test-store-ontology",
    )


# ============================================================
# Mock SPARQL
# ============================================================
@pytest.fixture
def mock_sparql_bindings():
    """标准 SPARQL bindings 响应"""
    return {
        "results": {
            "bindings": [
                {
                    "product_id": {"value": "P00001"},
                    "product_name": {"value": "伊利纯牛奶250ml"},
                    "remaining_days": {"value": "5"},
                    "shelf_date": {"value": "2025-05-15"},
                    "current_stock": {"value": "50"},
                },
            ]
        }
    }


# ============================================================
# Mock AgentState
# ============================================================
@pytest.fixture
def mock_agent_state():
    """标准 AgentState for testing"""
    from app.agent.state import AgentState
    state = AgentState(
        messages=[],
        session_id="test-session-001",
        user_id="u001",
        store_id="STORE_001",
        role="clerk",
        discount_task=None,
        expiring_products=[],
        tier_config={},
    )
    return state
