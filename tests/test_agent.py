"""
Test StoreBrainAgent components:
- SPARQLService queries
- Agent tools
"""

from app.services.sparql_service import SPARQLService
from app.agent.store_brain_agent import (
    query_pending_skus,
    query_clearance_rules,
    query_worktask,
    list_worktasks,
    reason_discount,
)


# ============================================================
# SPARQLService tests
# ============================================================

def test_sparql_service_initialization():
    """SPARQLService should load ontology graph on init"""
    sparql = SPARQLService()
    assert sparql.graph is not None
    assert len(sparql.graph) > 100  # At least 1000+ triples


def test_sparql_query_all_tasks():
    """get_all_tasks should return a list (empty or with results)"""
    sparql = SPARQLService()
    results = sparql.get_all_tasks(limit=10)
    assert isinstance(results, list)


def test_sparql_query_by_task_id():
    """get_task_by_id should return list (empty if not found)"""
    sparql = SPARQLService()
    results = sparql.get_task_by_id("NONEXISTENT-TASK-ID")
    assert isinstance(results, list)


# ============================================================
# Tool function tests
# ============================================================

def test_query_pending_skus_returns_json():
    """query_pending_skus should return valid JSON string"""
    result = query_pending_skus.invoke({})
    import json
    parsed = json.loads(result)
    assert "skus" in parsed
    assert "count" in parsed
    assert isinstance(parsed["skus"], list)


def test_query_clearance_rules_with_empty_uri():
    """query_clearance_rules should handle empty/fake category URI gracefully"""
    result = query_clearance_rules.invoke({"category_uri": "so:FakeCategory"})
    import json
    parsed = json.loads(result)
    assert parsed["found"] == False
    assert parsed["rules"] == []


def test_reason_discount_with_valid_data():
    """reason_discount should handle well-formed SKU data"""
    sku_data = {
        "name": "测试豆腐",
        "code": "P001",
        "quantity": 50,
        "expiry_date": "2026-04-25",
        "category_uri": "so:CategoryDailyFresh",
        "category_name": "日配",
    }
    result = reason_discount.invoke({"sku_data": sku_data})
    import json
    parsed = json.loads(result)
    assert "days_left" in parsed
    assert "recommended_discount" in parsed


def test_reason_discount_expired_product():
    """reason_discount should handle expired products (days_left < 0)"""
    sku_data = {
        "name": "过期豆腐",
        "code": "P999",
        "quantity": 50,
        "expiry_date": "2026-04-01",  # In the past
        "category_uri": "so:CategoryDailyFresh",
        "category_name": "日配",
    }
    result = reason_discount.invoke({"sku_data": sku_data})
    import json
    parsed = json.loads(result)
    assert parsed["days_left"] < 0
    assert parsed["recommended_discount"] is None