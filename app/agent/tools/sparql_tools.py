# ============================================================
# SPARQL 工具集 — Phase 2.4
# 通过 rdflib 查询 GraphDB SPARQL endpoint
# TBOX 规则在此文件中不硬编码，只做查询
# ============================================================
import httpx
from typing import Optional
from app.config import settings
from app.agent.state import ExpiringProduct


async def sparql_query(query: str, store_id: str) -> list[dict]:
    """
    通用 SPARQL 查询

    所有查询自动注入 store_id 过滤条件（来自 TBOX 设计原则）。
    """
    endpoint = settings.sparql_endpoint
    params = {
        "query": query,
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(endpoint, params=params)
            resp.raise_for_status()
            data = resp.json()

        # 解析 SPARQL JSON 结果
        results = []
        bindings = data.get("results", {}).get("bindings", [])
        for row in bindings:
            results.append({k: v.get("value") for k, v in row.items()})
        return results
    except httpx.HTTPError as e:
        return [{"error": f"SPARQL 查询失败: {str(e)}"}]


async def query_expiring_products(
    store_id: str,
    days: int = 7,
) -> list[ExpiringProduct]:
    """
    查询指定门店剩余保质期 ≤ N 天的商品

    SPARQL 逻辑：
    1. 找该门店所有商品
    2. 计算剩余保质期 = expirationDate - today
    3. 过滤 remaining_days ≤ days
    4. 排除豁免商品（ExemptProduct）
    """
    query = f"""
    PREFIX store: <http://store-ontology.org/ontology/>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX date: <http://www.w3.org/2000/10/swap/datetime#>

    SELECT ?product ?product_name ?category ?shelf_date ?expiration_date
           (xsd:integer(?exp_days) - xsd:integer(?today_days) AS ?remaining_days)
    WHERE {{
      ?product a store:Product .
      ?product store:productName ?product_name .
      ?product store:belongsToStore ?store .
      ?store store:storeId "{store_id}" .

      # 计算保质期天数（来自 TBOX shelfDate 属性）
      OPTIONAL {{ ?product store:shelfDate ?shelf_date }}
      BIND(IF(BOUND(?shelf_date), xsd:integer(?shelf_date), 0) AS ?exp_days)
      BIND(IF(BOUND(?shelf_date), xsd:integer(?shelf_date) - {days}, 0) AS ?today_days)

      OPTIONAL {{ ?product store:expirationDate ?expiration_date }}
      OPTIONAL {{ ?product store:belongsToCategory ?cat . ?cat store:categoryName ?category }}

      # 排除豁免商品
      FILTER NOT EXISTS {{ ?product a store:ExemptProduct }}

      # 过滤剩余保质期 ≤ N 天
      FILTER(?remaining_days <= {days})
    }}
    ORDER BY ASC(?remaining_days)
    LIMIT 50
    """

    rows = await sparql_query(query, store_id)

    products: list[ExpiringProduct] = []
    for row in rows:
        if "error" in row:
            continue
        products.append({
            "product_id": row.get("product", "").split("/")[-1],
            "product_name": row.get("product_name", "未知商品"),
            "category": row.get("category", "未分类"),
            "shelf_date_days": int(row.get("shelf_date", 0)),
            "expiration_date": row.get("expiration_date", ""),
            "remaining_days": int(row.get("remaining_days", 0)),
            "is_exempt": False,
        })

    return [p for p in products if 0 <= p["remaining_days"] <= days]


async def query_product_info(product_id: str, store_id: str) -> Optional[ExpiringProduct]:
    """查询单个商品的完整信息"""
    query = f"""
    PREFIX store: <http://store-ontology.org/ontology/>

    SELECT ?product_name ?category ?shelf_date ?expiration_date ?is_exempt
    WHERE {{
      ?product store:productId "{product_id}" .
      ?product store:productName ?product_name .
      OPTIONAL {{ ?product store:belongsToCategory ?cat . ?cat store:categoryName ?category }}
      OPTIONAL {{ ?product store:shelfDate ?shelf_date }}
      OPTIONAL {{ ?product store:expirationDate ?expiration_date }}
      BIND(EXISTS {{ ?product a store:ExemptProduct }} AS ?is_exempt)
    }}
    LIMIT 1
    """

    rows = await sparql_query(query, store_id)
    if not rows or "error" in rows[0]:
        return None

    row = rows[0]
    return {
        "product_id": product_id,
        "product_name": row.get("product_name", "未知商品"),
        "category": row.get("category", "未分类"),
        "shelf_date_days": int(row.get("shelf_date", 0)),
        "expiration_date": row.get("expiration_date", ""),
        "remaining_days": 0,
        "is_exempt": row.get("is_exempt", "false") == "true",
    }
