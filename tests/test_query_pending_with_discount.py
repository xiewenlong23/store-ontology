#!/usr/bin/env python3
"""
测试：query_pending_with_discount 组合工具 + query_discount 健壮化

TDD for:
1. query_pending_with_discount: 查询临期商品并同时给出折扣建议
2. query_discount 健壮化: 修复参数bug、边界case处理
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

# 触发工具注册
import app.tools.store_tools
from app.tools.registry import registry


class TestQueryPendingWithDiscountTool:
    """query_pending_with_discount 组合工具测试"""

    def test_tool_is_registered(self):
        """组合工具应该被注册"""
        tools = registry.get_all_tools()
        assert "query_pending_with_discount" in tools, f"Missing tool, have: {list(tools.keys())}"

    def test_tool_schema_has_required_fields(self):
        """schema 应包含 name, description, parameters"""
        entry = registry.get("query_pending_with_discount")
        assert entry is not None
        schema = entry.schema
        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema

    def test_tool_returns_pending_products_with_discount(self):
        """返回的每个商品都应包含折扣建议"""
        entry = registry.get("query_pending_with_discount")
        handler = entry.handler

        result = handler(
            category="daily_fresh",
            days_threshold=7,
            store_id="STORE-001",
        )

        assert result["success"] is True
        assert "products" in result
        products = result["products"]
        assert isinstance(products, list)
        for p in products:
            assert "product_id" in p
            assert "name" in p
            assert "days_left" in p
            assert "recommended_discount" in p

    def test_tool_with_no_pending_products(self):
        """没有临期商品时返回空列表"""
        entry = registry.get("query_pending_with_discount")
        handler = entry.handler

        result = handler(
            category="daily_fresh",
            days_threshold=0,  # 0天阈值，排除所有商品
            store_id="STORE-001",
        )

        assert result["success"] is True
        assert result["count"] == 0
        assert result["products"] == []

    def test_tool_filters_by_category(self):
        """按品类筛选"""
        entry = registry.get("query_pending_with_discount")
        handler = entry.handler

        result = handler(
            category="bakery",
            days_threshold=7,
        )

        assert result["success"] is True
        for p in result["products"]:
            assert p.get("category") == "bakery"

    def test_tool_filters_by_store_id(self):
        """按门店筛选"""
        entry = registry.get("query_pending_with_discount")
        handler = entry.handler

        result = handler(
            store_id="STORE-999",  # 不存在的门店
            days_threshold=7,
        )

        assert result["success"] is True
        assert result["count"] == 0


class TestQueryDiscountRobustness:
    """query_discount 健壮化测试"""

    def test_query_discount_with_all_params(self):
        """传入所有参数时应正常返回折扣建议"""
        entry = registry.get("query_discount")
        handler = entry.handler

        result = handler(
            product_id="P001",
            product_name="嫩豆腐",
            category="daily_fresh",
            expiry_date="2026-04-23",
            stock=50,
        )

        assert result["success"] is True
        assert "recommended_discount" in result
        assert "tier" in result

    def test_query_discount_explain_mode(self):
        """传入 discount_rate 时为解释型查询"""
        entry = registry.get("query_discount")
        handler = entry.handler

        result = handler(
            product_name="嫩豆腐",
            category="daily_fresh",
            expiry_date="2026-04-23",
            stock=50,
            discount_rate=0.4,
        )

        assert result["success"] is True
        assert "explanation" in result or "reasoning" in result

    def test_query_discount_handles_expired_product(self):
        """已过期商品应返回错误或特殊处理"""
        entry = registry.get("query_discount")
        handler = entry.handler

        # 过期商品（假设今天不是2026年4月21日）
        result = handler(
            product_name="测试商品",
            category="daily_fresh",
            expiry_date="2026-04-19",  # 已经是过去
            stock=50,
        )

        # 应该优雅处理，不抛出异常
        assert isinstance(result, dict)
        # 过期商品 days_left < 0 时的行为由实现决定

    def test_query_discount_without_category_defaults_to_daily_fresh(self):
        """未传品类时默认使用 daily_fresh"""
        entry = registry.get("query_discount")
        handler = entry.handler

        result = handler(
            product_name="测试商品",
            expiry_date="2026-04-25",
            stock=30,
        )

        assert result["success"] is True

    def test_query_discount_ttl_query_not_failing(self):
        """TTL 查询不因多余参数失败"""
        # 这是关键回归测试：之前 days_left 参数导致调用失败
        entry = registry.get("query_discount")
        handler = entry.handler

        # 不应抛出异常（之前 ttl_query_clearance_rules 不接受 days_left）
        result = handler(
            product_name="测试商品",
            category="daily_fresh",
            expiry_date="2026-04-25",
            stock=30,
        )
        assert result["success"] is True


class TestExplainDiscountReasoningEdgeCases:
    """explain_discount_reasoning 边界 case 测试"""

    def test_explain_without_matched_rule(self):
        """无匹配规则时的处理"""
        from app.services.ttl_llm_reasoning import explain_discount_reasoning

        # 使用一个没有TTL规则的品类
        result = explain_discount_reasoning(
            product_id="TEST-EDGE",
            product_name="边缘商品",
            category="nonexistent_category",
            expiry_date="2026-04-25",
            stock=30,
            discount_rate=0.5,
        )

        assert result["success"] is True
        assert "explanation" in result

    def test_explain_with_no_rules_returned(self):
        """TTL 返回空规则列表时的处理"""
        from app.services.ttl_llm_reasoning import explain_discount_reasoning

        result = explain_discount_reasoning(
            product_id="TEST-EMPTY",
            product_name="空规则商品",
            category="daily_fresh",
            expiry_date="2026-04-23",
            stock=50,
            discount_rate=0.4,
        )

        assert result["success"] is True
        # 应优雅降级，不抛出异常