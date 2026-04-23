#!/usr/bin/env python3
"""
ABox 库存查询服务
直接从 products.json 查询临期货商品（不经过 SPARQL/TTL）
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PRODUCTS_FILE = Path(__file__).parent.parent.parent / "data" / "products.json"

# 缓存 products.json 内容，进程内单例
_cached_products: Optional[list[dict]] = None


def _load_products() -> list[dict]:
    """加载 products.json，带缓存。"""
    global _cached_products
    if _cached_products is None:
        try:
            with open(PRODUCTS_FILE, encoding="utf-8") as f:
                _cached_products = json.load(f)
            logger.info(f"[Inventory] Loaded {len(_cached_products)} products from {PRODUCTS_FILE}")
        except Exception as e:
            logger.error(f"[Inventory] Failed to load products.json: {e}")
            _cached_products = []
    return _cached_products


def query_pending_clearance_skus(days_threshold: int = 2) -> list[dict]:
    """
    从 products.json 查询临期货商品。

    Args:
        days_threshold: 剩余天数阈值，默认 ≤ 2 天

    Returns:
        临期货商品列表，每项包含：
        sku, name, qty, expiry, days_left, category, is_imported, is_organic,
        is_promoted, arrival_days, in_reduction
    """
    products = _load_products()
    today = date.today()
    result = []
    for p in products:
        try:
            expiry = date.fromisoformat(p["expiry_date"])
        except (ValueError, KeyError):
            continue
        days_left = (expiry - today).days
        if 0 <= days_left <= days_threshold and not p.get("in_reduction", False):
            result.append({
                "sku": p["product_id"],
                "name": p["name"],
                "qty": p.get("stock", 0),
                "expiry": p["expiry_date"],
                "days_left": days_left,
                "category": p.get("category", ""),
                "is_imported": p.get("is_imported", False),
                "is_organic": p.get("is_organic", False),
                "is_promoted": p.get("is_promoted", False),
                "arrival_days": p.get("arrival_days"),
                "in_reduction": p.get("in_reduction", False),
            })
    logger.info(f"[Inventory] Found {len(result)} pending clearance SKUs (days_threshold={days_threshold})")
    return result


def get_product_by_sku(sku: str) -> Optional[dict]:
    """根据 SKU 查询商品详情。"""
    products = _load_products()
    for p in products:
        if p.get("product_id") == sku:
            return p
    return None


def check_product_exemption_from_json(product: dict) -> Optional[dict]:
    """
    基于商品属性（来自 JSON）判断豁免类型。

    Args:
        product: 商品字典，应包含 is_imported, is_organic, is_promoted, arrival_days

    Returns:
        豁免信息dict或None
    """
    if product.get("is_imported"):
        return {"exemption_type": "imported", "exemption_reason": "进口商品不参与临期打折", "rule_source": "headquarters"}
    if product.get("is_organic"):
        return {"exemption_type": "organic", "exemption_reason": "有机绿色食品不参与临期打折", "rule_source": "headquarters"}
    if product.get("is_promoted"):
        return {"exemption_type": "already_promoted", "exemption_reason": "已参与促销不叠加折扣", "rule_source": "headquarters"}
    arrival_days = product.get("arrival_days")
    if arrival_days is not None and arrival_days <= 7:
        return {"exemption_type": "new_arrival", "exemption_reason": f"新上架商品(到货{arrival_days}天)不参与", "rule_source": "headquarters"}
    return None