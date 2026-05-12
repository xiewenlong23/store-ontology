"""
tests/unit/test_sparql_tools.py — Phase 7.1
SPARQL 工具单元测试（Mock GraphDB 响应）
"""
import pytest
from unittest.mock import patch, AsyncMock


class MockSparqlResult:
    """Mock SPARQL 查询结果"""
    def __init__(self, bindings: list):
        self.bindings = bindings
        self.head = {"vars": []}


@pytest.mark.asyncio
@patch("app.agent.tools.sparql_tools._sparql_query")
async def test_query_expiring_products(mock_sparql_query):
    """临期商品查询：返回在架期 ≤N 天的商品"""
    from app.agent.tools.sparql_tools import query_expiring_products

    mock_sparql_query.return_value = {
        "results": {
            "bindings": [
                {
                    "product_id": {"value": "P00001"},
                    "product_name": {"value": "伊利纯牛奶250ml"},
                    "remaining_days": {"value": "5"},
                    "shelf_date": {"value": "2025-05-15"},
                },
            ]
        }
    }

    result = await query_expiring_products(store_id="STORE_001", days=7)

    assert result["count"] == 1
    assert result["products"][0]["product_id"] == "P00001"
    assert result["products"][0]["remaining_days"] == 5
    mock_sparql_query.assert_called_once()


@pytest.mark.asyncio
@patch("app.agent.tools.sparql_tools._sparql_query")
async def test_query_product_info(mock_sparql_query):
    """商品信息查询"""
    from app.agent.tools.sparql_tools import query_product_info

    mock_sparql_query.return_value = {
        "results": {
            "bindings": [
                {
                    "name": {"value": "伊利纯牛奶250ml"},
                    "category": {"value": "乳制品"},
                    "retail_price": {"value": "59.00"},
                    "cost_price": {"value": "45.60"},
                    "supplier": {"value": "伊利集团华东分公司"},
                },
            ]
        }
    }

    result = await query_product_info(product_id="P00001", store_id="STORE_001")

    assert result["name"] == "伊利纯牛奶250ml"
    assert result["category"] == "乳制品"
    assert float(result["retail_price"]) == 59.00


@pytest.mark.asyncio
@patch("app.agent.tools.sparql_tools._sparql_query")
async def test_sparql_query_error(mock_sparql_query):
    """SPARQL 查询异常处理"""
    from app.agent.tools.sparql_tools import query_product_info

    mock_sparql_query.side_effect = Exception("GraphDB connection refused")

    result = await query_product_info(product_id="P00001", store_id="STORE_001")

    assert "error" in result
    assert "GraphDB" in result["error"]
