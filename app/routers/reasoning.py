from fastapi import APIRouter
from pydantic import BaseModel
from app.models import ProductCategory
from datetime import date
from pathlib import Path
from typing import Optional, List
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"

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

# Module-level constants for SPARQL category URI mapping
# 注意：URI 值必须与 TTL 本体中 appliesToCategory 的实际取值完全一致（无 Category 前缀）
CATEGORY_URI_MAP = {
    "daily_fresh": "https://store-ontology.example.com/retail#DailyFresh",
    "bakery": "https://store-ontology.example.com/retail#Bakery",
    "fresh": "https://store-ontology.example.com/retail#FreshProduce",
    "meat_poultry": "https://store-ontology.example.com/retail#MeatPoultry",
    "seafood": "https://store-ontology.example.com/retail#Seafood",
    "dairy": "https://store-ontology.example.com/retail#Dairy",
    "frozen": "https://store-ontology.example.com/retail#FrozenFood",
    "beverage": "https://store-ontology.example.com/retail#Beverage",
    "snack": "https://store-ontology.example.com/retail#SnackFood",
    "grain_oil": "https://store-ontology.example.com/retail#RiceGrainOil",
}

# Tier priority ordering for urgency matching
TIER_PRIORITY = {
    "UrgencyCritical": 0,
    "UrgencyHigh": 1,
    "UrgencyMedium": 2,
    "UrgencyLow": 3,
    "UrgencyPreventive": 4,
}

# Tier name to number mapping (extracted from tier name strings)
_TIER_NAME_TO_NUM = {
    "TierShelfLife1Day": 1,
    "TierShelfLife2to3Days": 2,
    "TierShelfLife4to7Days": 3,
    "TierShelfLife8to14Days": 4,
    "TierShelfLife15to30Days": 5,
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
    discount_range: List[float]
    tier: int
    reasoning: str
    auto_create_task: bool = False
    # 豁免信息
    exemption_type: Optional[str] = None
    exemption_reason: Optional[str] = None
    is_exempted: bool = False
    # AI自动确认
    auto_confirmed: bool = False
    risk_level: Optional[str] = None

@router.get("/products")
def list_products():
    """Return product list from products.json."""
    try:
        if not PRODUCTS_FILE.exists():
            logger.error(f"Products file not found: {PRODUCTS_FILE}")
            return {"error": "Product data unavailable", "products": []}
        with open(PRODUCTS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load products: {e}")
        return {"error": f"Failed to load products: {e}", "products": []}

@router.post("/discount", response_model=ReasoningResponse)
def recommend_discount(req: ReasoningRequest):
    """
    基于 TTL 本体 SPARQL 推理的折扣推荐。

    查询本体中的折扣规则，按剩余保质期匹配 tier。
    """
    from app.services.sparql_service import SPARQLService

    today = date.today()
    days_left = (req.expiry_date - today).days

    if days_left < 0:
        return ReasoningResponse(
            product_id=req.product_id,
            recommended_discount=0.0,
            discount_range=[0.0, 0.0],
            tier=0,
            reasoning=f"商品已过期 {abs(days_left)} 天，无法折扣",
            auto_create_task=False,
        )

    sparql = SPARQLService()

    # 查找对应品类的 URI
    category_uri = CATEGORY_URI_MAP.get(req.category.value)
    rules = sparql.query_clearance_rules(category_uri) if category_uri else []

    # 匹配 tier
    matched = None
    best_priority = 99

    for r in rules:
        tier_min = int(r.tierMin)
        tier_max = int(r.tierMax)
        if tier_min <= days_left <= tier_max:
            urgency_name = str(r.urgency).split("#")[-1]
            priority = TIER_PRIORITY.get(urgency_name, 99)
            if priority < best_priority:
                matched = r
                best_priority = priority

    if matched:
        rec = float(matched.recDiscount)
        min_d = float(matched.minDiscount)
        max_d = float(matched.maxDiscount)
        tier_name = str(matched.tier).split("#")[-1]
        reasoning = (
            f"剩余保质期 {days_left} 天，匹配 [{tier_name}]，"
            f"规则允许折扣 {min_d*100:.0f}%-{max_d*100:.0f}%，推荐 {rec*100:.0f}%"
        )
        auto_create = days_left <= 1
        discount_range = [min_d, max_d]
        # 从 tier 名称解析 tier 编号
        tier = next((num for name, num in _TIER_NAME_TO_NUM.items() if name in tier_name), 1)
    else:
        # ⚠️ SYNC WARNING: 降级规则硬编码于此，需手动保持与 TTL 本体一致
        # 当前降级规则值（必须与 WORKTASK-MODULE.ttl 中的 sp:defaultRecDiscount 一致）:
        #   T1 (0-1天): rec=20%, range=10%-50%
        #   T2 (2-3天): rec=40%, range=30%-60%
        #   T3 (4-7天): rec=70%, range=50%-80%
        #   T4 (8-14天): rec=85%, range=70%-90%
        #   T5 (15-30天): rec=95%, range=90%-100%
        # 修改此处规则后必须同步修改 TTL 本体中的对应 triples
        if days_left <= 1:
            tier, rec, min_d, max_d = 1, 0.20, 0.10, 0.50
        elif days_left <= 3:
            tier, rec, min_d, max_d = 2, 0.40, 0.30, 0.60
        elif days_left <= 7:
            tier, rec, min_d, max_d = 3, 0.70, 0.50, 0.80
        elif days_left <= 14:
            tier, rec, min_d, max_d = 4, 0.85, 0.70, 0.90
        else:
            tier, rec, min_d, max_d = 5, 0.95, 0.90, 1.00

        reasoning = f"标准 tier T{tier} 定价（无本体规则时降级）"
        auto_create = days_left <= 1
        discount_range = [min_d, max_d]

    # 库存调整
    if req.stock > 100 and days_left <= 2:
        rec = min(rec * 0.8, 0.30)
        reasoning += f"；高库存 ({req.stock}) + 短有效期 → 激进折扣"
        auto_create = True

    # 豁免检查（接入本体推理）
    exemption = sparql.check_product_exemption(
        product_id=req.product_id,
        category_uri=category_uri or "",
        is_imported=False,  # TODO: 从商品属性获取
        is_organic=False,    # TODO: 从商品属性获取
        is_promoted=False,   # TODO: 从商品属性获取
        arrival_days=None,   # TODO: 从商品属性获取
    )

    is_exempted = exemption is not None
    exemption_type: Optional[str] = None
    exemption_reason: Optional[str] = None

    if is_exempted:
        exemption_type = exemption["exemption_type"]
        exemption_reason = exemption["exemption_reason"]
        reasoning += f"；【豁免】{exemption_reason}"
        # 豁免商品不创建任务
        auto_create = False

    # AI 自动确认阈值评估
    from app.services.auto_confirm_service import should_auto_confirm
    auto_confirmed, risk_level, risk_reason = should_auto_confirm(
        discount_rate=rec,
        stock=req.stock,
        days_left=days_left,
        category=req.category,
    )
    reasoning += f"；风险评估: {risk_reason}"

    return ReasoningResponse(
        product_id=req.product_id,
        recommended_discount=rec,
        discount_range=discount_range,
        tier=tier,
        reasoning=reasoning,
        auto_create_task=auto_create,
        exemption_type=exemption_type,
        exemption_reason=exemption_reason,
        is_exempted=is_exempted,
        auto_confirmed=auto_confirmed,
        risk_level=risk_level.value if risk_level else None,
    )

@router.post("/agent/scan")
def agent_scan_products():
    """
    扫描所有商品，触发库存事件并返回待创建任务列表。

    事件驱动：每个临期商品发出 InventoryEvent，
    触发推理引擎进行折扣推荐。
    """
    try:
        with open(PRODUCTS_FILE) as f:
            products = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"[Reasoning] Failed to read products file: {e}")
        return []

    tasks_to_create = []
    today = date.today()

    # 事件总线
    from app.services.event_system import get_event_bus, EventType
    event_bus = get_event_bus()

    for p in products:
        expiry = date.fromisoformat(p["expiry_date"])
        days_left = (expiry - today).days

        # 发出库存事件（无论是否临期，用于监控）
        if days_left <= 2:
            event_type = (
                EventType.INVENTORY_SHELF_LIFE_CRITICAL if days_left <= 1
                else EventType.INVENTORY_SHELF_LIFE_WARNING
            )
            event_bus.emit_inventory_event(
                event_type=event_type,
                product_id=p["product_id"],
                product_name=p["name"],
                category=p["category"],
                stock=p["stock"],
                expiry_date=p["expiry_date"],
                days_left=days_left,
            )

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
                    "reasoning": resp.reasoning,
                    "auto_confirmed": resp.auto_confirmed,
                    "risk_level": resp.risk_level,
                    "exemption_type": resp.exemption_type,
                    "is_exempted": resp.is_exempted,
                })

    return {
        "tasks_to_create": tasks_to_create,
        "scanned_count": len(products),
        "events_emitted": True,
    }


@router.post("/scan/trigger")
def trigger_scan_now():
    """
    手动触发立即库存扫描（绕过定时器）。
    用于测试或手动干预。
    """
    try:
        from app.services.scheduler_service import trigger_inventory_scan_now
        trigger_inventory_scan_now()
        return {"status": "triggered", "message": "库存扫描已手动触发"}
    except Exception as e:
        logger.error(f"[Reasoning] Manual scan trigger failed: {e}")
        return {"status": "error", "message": str(e)}
