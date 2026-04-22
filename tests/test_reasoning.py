from app.routers.reasoning import recommend_discount, ReasoningRequest
from app.models import ProductCategory
from datetime import date

def test_tier1_high_stock():
    req = ReasoningRequest(
        product_id="P001",
        product_name="嫩豆腐",
        category=ProductCategory.DAILY_FRESH,
        expiry_date=date(2026, 4, 23),
        stock=150
    )
    resp = recommend_discount(req)
    assert resp.tier == 1
    assert resp.recommended_discount < 0.30
    assert resp.auto_create_task == True

def test_tier4_normal():
    req = ReasoningRequest(
        product_id="P004",
        product_name="蒙牛特仑苏",
        category=ProductCategory.DAIRY,
        expiry_date=date(2026, 5, 1),
        stock=50
    )
    resp = recommend_discount(req)
    assert resp.tier == 4
    assert resp.auto_create_task == False
