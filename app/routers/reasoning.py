from fastapi import APIRouter
from pydantic import BaseModel
from app.models import ProductCategory
from datetime import date
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

DISCOUNT_TIERS = {
    1: (0.10, 0.50, 0.20),   # T1: 0-1 days -> 10-50%, rec 20%
    2: (0.30, 0.60, 0.40),   # T2: 2-3 days -> 30-60%, rec 40%
    3: (0.50, 0.80, 0.70),   # T3: 4-7 days -> 50-80%, rec 70%
    4: (0.70, 0.90, 0.85),   # T4: 8-14 days -> 70-90%, rec 85%
    5: (0.90, 1.00, 0.95),   # T5: 15-30 days -> 90-100%, rec 95%
}

URGENCY_MAP = {
    ProductCategory.DAILY_FRESH: 1,
    ProductCategory.BAKERY: 1,
    ProductCategory.FRESH: 3,
    ProductCategory.MEAT_POULTRY: 5,
    ProductCategory.SEAFOOD: 3,
    ProductCategory.DAIRY: 7,
    ProductCategory.FROZEN: 30,
    ProductCategory.BEVERAGE: 60,
    ProductCategory.SNACK: 90,
    ProductCategory.GRAIN_OIL: 180,
}

class ReasoningRequest(BaseModel):
    product_id: str
    product_name: str
    category: ProductCategory
    expiry_date: date
    stock: int

class ReasoningResponse(BaseModel):
    product_id: str
    recommended_discount: float
    discount_range: list[float]
    tier: int
    reasoning: str
    auto_create_task: bool = False

@router.get("/products")
def list_products():
    """Return mock product list for the dashboard."""
    return [
        {"product_id": "P001", "name": "嫩豆腐", "category": "daily_fresh", "expiry_date": "2026-04-21", "stock": 50, "in_reduction": False},
        {"product_id": "P002", "name": "现烤法式面包", "category": "bakery", "expiry_date": "2026-04-20", "stock": 30, "in_reduction": False},
        {"product_id": "P003", "name": "红富士苹果", "category": "fresh", "expiry_date": "2026-04-22", "stock": 80, "in_reduction": False},
    ]

@router.post("/discount", response_model=ReasoningResponse)
def recommend_discount(req: ReasoningRequest):
    today = date.today()
    days_left = (req.expiry_date - today).days

    if days_left <= 1:
        tier = 1
    elif days_left <= 3:
        tier = 2
    elif days_left <= 7:
        tier = 3
    elif days_left <= 14:
        tier = 4
    else:
        tier = 5
    discount_range, rec = DISCOUNT_TIERS[tier][:2], DISCOUNT_TIERS[tier][2]

    # Adjust based on stock volume
    if req.stock > 100 and days_left <= 2:
        rec = min(rec * 0.8, 0.30)
        reasoning = f"High stock ({req.stock}) + short expiry ({days_left} days) -> aggressive discount"
        auto_create = True
    else:
        reasoning = f"Standard tier T{tier} pricing"
        auto_create = days_left <= 1

    return ReasoningResponse(
        product_id=req.product_id,
        recommended_discount=rec,
        discount_range=discount_range,
        tier=tier,
        reasoning=reasoning,
        auto_create_task=auto_create
    )

@router.post("/agent/scan")
def agent_scan_products():
    with open("app/data/products.json") as f:
        products = json.load(f)

    tasks_to_create = []
    today = date.today()
    for p in products:
        expiry = date.fromisoformat(p["expiry_date"])
        days_left = (expiry - today).days
        if days_left <= 2 and not p.get("in_reduction"):
            try:
                category = ProductCategory(p["category"])
            except ValueError:
                logger.warning(f"Skipping product {p.get('product_id', 'unknown')}: invalid category '{p.get('category')}'")
                continue
            req = ReasoningRequest(
                product_id=p["product_id"],
                product_name=p["name"],
                category=category,
                expiry_date=expiry,
                stock=p["stock"]
            )
            resp = recommend_discount(req)
            if resp.auto_create_task:
                tasks_to_create.append({
                    "product_id": p["product_id"],
                    "recommended_discount": resp.recommended_discount,
                    "reasoning": resp.reasoning
                })

    return {"tasks_to_create": tasks_to_create}
