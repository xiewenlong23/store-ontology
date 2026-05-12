# ============================================================
# SPARQL 工具测试 — 按实际 sparql_tools.py 实现重写
# ============================================================
# 注：sparql_query 内部调用 httpx.AsyncClient，mock 层次在 sparql_query 上。
# 直接 mock httpx 的测试容易出错且与实现耦合，删除。
# 业务逻辑由 query_expiring_products / query_product_info 覆盖。
# ============================================================
import pytest
from unittest.mock import patch, AsyncMock


class TestQueryExpiringProducts:
    """测试临期商品查询"""

    @pytest.mark.asyncio
    async def test_query_expiring_products(self):
        """
        query_expiring_products 调用 sparql_query，
        后者解析 bindings → 返回展平的 dict list。
        mock sparql_query 直接返回已展平的格式（sparql_query 的实际输出）。
        """
        # sparql_query 解析 bindings 后的实际输出格式
        sparql_output = [
            {
                "product": "http://store-ontology.org/product/P001",
                "product_name": "牛奶",
                "category": "dairy",
                "shelf_date": "10",
                "expiration_date": "2025-01-15",
                "remaining_days": "3",
            }
        ]

        with patch("app.agent.tools.sparql_tools.sparql_query", new_callable=AsyncMock) as mock_sparql:
            mock_sparql.return_value = sparql_output
            from app.agent.tools.sparql_tools import query_expiring_products
            products = await query_expiring_products(store_id="STORE_001", days=7)

        assert len(products) == 1
        assert products[0]["product_id"] == "P001"
        assert products[0]["product_name"] == "牛奶"
        assert products[0]["remaining_days"] == 3

    @pytest.mark.asyncio
    async def test_query_expiring_products_error_row_skipped(self):
        """SPARQL 返回 error 条目时被跳过"""
        sparql_output = [
            {"error": "Connection refused"},
            {
                "product": "http://store-ontology.org/product/P001",
                "product_name": "牛奶",
                "category": "dairy",
                "shelf_date": "10",
                "expiration_date": "",
                "remaining_days": "5",
            },
        ]

        with patch("app.agent.tools.sparql_tools.sparql_query", new_callable=AsyncMock) as mock_sparql:
            mock_sparql.return_value = sparql_output
            from app.agent.tools.sparql_tools import query_expiring_products
            products = await query_expiring_products(store_id="STORE_001", days=7)

        assert len(products) == 1
        assert products[0]["product_id"] == "P001"


class TestQueryProductInfo:
    """测试商品信息查询"""

    @pytest.mark.asyncio
    async def test_query_product_info_found(self):
        """商品存在时返回完整信息"""
        sparql_output = [
            {
                "product_name": "牛奶",
                "category": "dairy",
                "shelf_date": "10",
                "expiration_date": "2025-01-15",
                "is_exempt": "false",
            }
        ]

        with patch("app.agent.tools.sparql_tools.sparql_query", new_callable=AsyncMock) as mock_sparql:
            mock_sparql.return_value = sparql_output
            from app.agent.tools.sparql_tools import query_product_info
            product = await query_product_info("P001", "STORE_001")

        assert product is not None
        assert product["product_id"] == "P001"
        assert product["product_name"] == "牛奶"
        assert product["is_exempt"] is False

    @pytest.mark.asyncio
    async def test_query_product_info_not_found(self):
        """商品不存在时返回 None"""
        sparql_output = []

        with patch("app.agent.tools.sparql_tools.sparql_query", new_callable=AsyncMock) as mock_sparql:
            mock_sparql.return_value = sparql_output
            from app.agent.tools.sparql_tools import query_product_info
            product = await query_product_info("UNKNOWN", "STORE_001")

        assert product is None

    @pytest.mark.asyncio
    async def test_query_product_info_error(self):
        """SPARQL 返回 error 时返回 None"""
        with patch("app.agent.tools.sparql_tools.sparql_query", new_callable=AsyncMock) as mock_sparql:
            mock_sparql.return_value = [{"error": "Connection refused"}]
            from app.agent.tools.sparql_tools import query_product_info
            product = await query_product_info("P001", "STORE_001")

        assert product is None
