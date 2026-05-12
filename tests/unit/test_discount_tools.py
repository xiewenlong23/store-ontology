"""
tests/unit/test_discount_tools.py — Phase 7.1
折扣工具单元测试（Mock SPARQL）
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.agent.tools.discount_tools import (
    calculate_discount_tier,
    create_discount_task,
    query_discount_task,
)


class MockState:
    """Mock AgentState"""
    def __init__(self):
        self.messages = []          # ⭐ Fix #4：discount_tools 依赖 messages.append
        self.discount_task = None
        self.session_id = "test-session"
        self.user_id = "u001"
        self.store_id = "STORE_001"
        self.role = "clerk"
        self.expiring_products = []
        self.tier_config = {}


class MockSparqlResult:
    """Mock SPARQL 查询结果"""
    def __init__(self, data):
        self.data = data


@patch("app.agent.tools.discount_tools.query_sparql")
@patch("app.agent.tools.discount_tools.write_audit_log")
async def test_calculate_discount_tier_normal_product(mock_audit, mock_sparql):
    """普通商品：正常折扣率 → tier=1"""
    mock_sparql.return_value = MockSparqlResult({
        "expiry_date": {"value": "2025-06-01"},
        "current_stock": {"value": "50"},
    })

    result = await calculate_discount_tier(
        product_id="P00001",
        original_price=100.0,
        discount_rate=0.15,
        state=MockState(),
    )

    assert result["tier"] == 1
    assert result["discount_rate"] == 0.15
    assert result["final_price"] == 85.0
    assert result["requires_approval"] is False
    mock_audit.assert_called_once()


@patch("app.agent.tools.discount_tools.query_sparql")
@patch("app.agent.tools.discount_tools.write_audit_log")
async def test_calculate_discount_tier_expiring_product(mock_audit, mock_sparql):
    """临期商品：折扣率放宽到 tier=2"""
    mock_sparql.return_value = MockSparqlResult({
        "expiry_date": {"value": "2025-05-20"},  # 距今8天
        "current_stock": {"value": "50"},
    })

    result = await calculate_discount_tier(
        product_id="P00001",
        original_price=100.0,
        discount_rate=0.30,
        state=MockState(),
    )

    assert result["tier"] == 2
    assert result["requires_approval"] is False  # tier2 仍在阈值内


@patch("app.agent.tools.discount_tools.query_sparql")
@patch("app.agent.tools.discount_tools.write_audit_log")
async def test_calculate_discount_tier_exceeds_tier2(mock_audit, mock_sparql):
    """商品折扣率超 tier2 阈值：需要审批"""
    mock_sparql.return_value = MockSparqlResult({
        "expiry_date": {"value": "2025-06-01"},
        "current_stock": {"value": "50"},
    })

    result = await calculate_discount_tier(
        product_id="P00001",
        original_price=100.0,
        discount_rate=0.40,
        state=MockState(),
    )

    assert result["tier"] == 3
    assert result["requires_approval"] is True  # tier3 需要审批


@patch("app.agent.tools.discount_tools.query_sparql")
@patch("app.agent.tools.discount_tools.write_audit_log")
async def test_create_discount_task_stores_in_state(mock_audit, mock_sparql):
    """create_discount_task 将任务写入 state"""
    mock_sparql.return_value = MockSparqlResult({
        "expiry_date": {"value": "2025-06-01"},
        "current_stock": {"value": "50"},
    })

    state = MockState()
    result = await create_discount_task(
        product_id="P00001",
        discount_rate=0.20,
        state=state,
    )

    assert result["task_id"] is not None
    assert result["status"] == "pending_approval"
    assert state.discount_task is not None
    assert state.discount_task["product_id"] == "P00001"
