"""
Tests for TTL+LLM layered reasoning engine
"""

import pytest
from datetime import date, timedelta

from app.services.complexity_classifier import (
    get_complexity_classifier,
    QueryComplexity,
)
from app.services.ttl_llm_reasoning import (
    ttl_query_pending_skus,
    ttl_query_clearance_rules,
    ttl_query_tasks,
    ttl_query_exemption_rules,
    reason_discount_llm,
    assess_risk_llm,
    _build_ttl_context_for_discount,
)
from app.models import ProductCategory


# ============================================================
# Complexity Classifier Tests
# ============================================================

def test_complexity_simple_list_query():
    """简单查询：列出临期商品 → Layer 1"""
    classifier = get_complexity_classifier()

    result = classifier.classify("列出所有临期商品")
    assert result == QueryComplexity.SIMPLE


def test_complexity_simple_task_list():
    """简单查询：任务列表 → Layer 1"""
    classifier = get_complexity_classifier()

    result = classifier.classify("查看当前有哪些任务")
    assert result == QueryComplexity.SIMPLE


def test_complexity_complex_discount():
    """复杂查询：折扣建议 → Layer 2"""
    classifier = get_complexity_classifier()

    result = classifier.classify("这件豆腐应该打几折")
    assert result == QueryComplexity.COMPLEX


def test_complexity_complex_why():
    """复杂查询：问原因 → Layer 2"""
    classifier = get_complexity_classifier()

    result = classifier.classify("为什么要推荐这个折扣")
    assert result == QueryComplexity.COMPLEX


def test_complexity_complex_recommend():
    """复杂查询：推荐建议 → Layer 2"""
    classifier = get_complexity_classifier()

    result = classifier.classify("推荐一个折扣方案")
    assert result == QueryComplexity.COMPLEX


def test_complexity_complex_risk():
    """复杂查询：风险评估 → Layer 2"""
    classifier = get_complexity_classifier()

    result = classifier.classify("这个方案有没有风险")
    assert result == QueryComplexity.COMPLEX


def test_complexity_classify_with_reason():
    """复杂度分类返回原因"""
    classifier = get_complexity_classifier()

    complexity, reason = classifier.classify_with_reason("应该打几折")
    assert complexity == QueryComplexity.COMPLEX
    assert "复杂" in reason or "模式" in reason


# ============================================================
# TTL Layer 1 Tests
# ============================================================

def test_ttl_query_clearance_rules_daily_fresh():
    """Layer 1: 日配品类规则查询（URI 已修复）"""
    result = ttl_query_clearance_rules("daily_fresh")
    assert result["found"] == True
    assert len(result["rules"]) >= 2  # T1 + T2
    assert result["layer"] == 1
    assert result["source"] == "ttl"


def test_ttl_query_clearance_rules_unknown_category():
    """Layer 1: 未知品类返回空"""
    result = ttl_query_clearance_rules("unknown_category")
    assert result["found"] == False
    assert result["rules"] == []


def test_ttl_query_exemption_rules():
    """Layer 1: 豁免规则查询"""
    result = ttl_query_exemption_rules()
    assert result["layer"] == 1
    assert result["source"] == "ttl"


def test_ttl_query_pending_skus():
    """Layer 1: 待出清 SKU 查询"""
    result = ttl_query_pending_skus()
    assert "skus" in result
    assert "count" in result
    assert result["layer"] == 1
    assert result["source"] == "ttl"


def test_ttl_query_tasks():
    """Layer 1: 任务列表查询"""
    result = ttl_query_tasks()
    assert "tasks" in result
    assert "count" in result
    assert result["layer"] == 1
    assert result["source"] == "ttl"


# ============================================================
# TTL Context Builder
# ============================================================

def test_build_ttl_context_daily_fresh():
    """TTL 上下文构建：日配"""
    context = _build_ttl_context_for_discount(
        category="daily_fresh",
        days_left=1,
        stock=50,
        product_name="嫩豆腐",
    )
    assert "嫩豆腐" in context
    assert "daily_fresh" in context
    assert "1" in context  # 1天
    assert "50" in context  # 库存


# ============================================================
# Discount Reasoning Layer 2 Tests
# ============================================================

def test_reason_discount_llm_tier1_no_llm():
    """Layer 2 (TTL only): 日配 T1 折扣推理"""
    today = date.today()
    result = reason_discount_llm(
        product_id="TEST001",
        product_name="嫩豆腐",
        category=ProductCategory.DAILY_FRESH,
        expiry_date=today + timedelta(days=1),
        stock=50,
        use_llm=False,  # 不用 LLM，只测 TTL
    )
    assert result["recommended_discount"] == 0.20
    assert result["tier"] == 1
    assert result["layer"] == 1  # use_llm=False 走 layer 1
    assert result["source"] == "ttl"
    assert result["is_exempted"] == False


def test_reason_discount_llm_tier2():
    """Layer 2 (TTL only): 日配 T2 折扣推理"""
    today = date.today()
    result = reason_discount_llm(
        product_id="TEST002",
        product_name="豆浆",
        category=ProductCategory.DAILY_FRESH,
        expiry_date=today + timedelta(days=2),
        stock=30,
        use_llm=False,
    )
    assert result["recommended_discount"] == 0.40
    assert result["tier"] == 2


def test_reason_discount_expired():
    """Layer 2: 已过期商品"""
    today = date.today()
    result = reason_discount_llm(
        product_id="TEST003",
        product_name="过期豆腐",
        category=ProductCategory.DAILY_FRESH,
        expiry_date=today - timedelta(days=1),
        stock=50,
        use_llm=False,
    )
    assert result["recommended_discount"] is None
    assert result["reasoning"] is not None


def test_reason_discount_high_stock_adjustment():
    """Layer 2: 高库存 + 短有效期触发折扣调整"""
    today = date.today()
    result = reason_discount_llm(
        product_id="TEST004",
        product_name="嫩豆腐",
        category=ProductCategory.DAILY_FRESH,
        expiry_date=today + timedelta(days=1),
        stock=150,  # > 100
        use_llm=False,
    )
    # 20% * 0.8 = 16%，上限 30%
    assert result["recommended_discount"] == pytest.approx(0.16)


def test_reason_discount_ttl_rules_applied():
    """Layer 2: 确认使用了 TTL 规则而非 fallback"""
    today = date.today()
    result = reason_discount_llm(
        product_id="TEST005",
        product_name="嫩豆腐",
        category=ProductCategory.DAILY_FRESH,
        expiry_date=today + timedelta(days=1),
        stock=50,
        use_llm=False,
    )
    # TTL URI 已修复，应该匹配 TierShelfLife1Day
    assert result["tier_name"] == "TierShelfLife1Day"
    assert result["source"] == "ttl"


# ============================================================
# Risk Assessment Tests
# ============================================================

def test_assess_risk_llm_low():
    """Layer 2: 低风险评估"""
    result = assess_risk_llm(
        discount_rate=0.2,
        stock=30,
        days_left=2,
        category=ProductCategory.DAILY_FRESH,
        use_llm=False,
    )
    assert result["risk_level"] == "low"
    assert result["auto_confirm"] == True
    assert result["source"] == "ttl"


def test_assess_risk_llm_high():
    """Layer 2: 高风险评估"""
    result = assess_risk_llm(
        discount_rate=0.8,
        stock=200,
        days_left=1,
        category=ProductCategory.FROZEN,  # 非敏感品类，可评估为 HIGH
        use_llm=False,
    )
    assert result["risk_level"] == "high"
    assert result["auto_confirm"] == False
    assert result["source"] == "ttl"


def test_assess_risk_llm_excluded_category():
    """Layer 2: 敏感品类禁止自动确认"""
    result = assess_risk_llm(
        discount_rate=0.2,  # 低折扣
        stock=30,  # 正常库存
        days_left=3,
        category=ProductCategory.MEAT_POULTRY,  # 在黑名单中
        use_llm=False,
    )
    # 肉禽在黑名单，即使低风险也需人工确认
    assert result["auto_confirm"] == False
