"""clearance 价值链流程的专属工具（P2 迁移自 verticals/clearance/tools.py）。

复用内核装配 _get_repo，按 customer 过滤。无折扣概念时本流程仍可用。
"""
from typing import Optional

from langchain_core.tools import tool

from ontology import tools as _tools_mod
from ontology.tools import _wrap
from business.discount import calculate_discount


@tool
def query_near_expiry(store_id: Optional[str] = None,
                      customer_id: str = "customer_default",
                      org_unit_id: str = "*") -> str:
    """查询临期商品列表（折扣来自单一事实源 calculate_discount）。"""
    from ontology.tenant import TenantContext
    tc = TenantContext(customer_id=customer_id, org_unit_id=org_unit_id)
    repo = _tools_mod._get_repo(tc)  # 延迟引用，支持 monkeypatch
    rows = repo.read("NearExpiryProduct", tc)
    if store_id:
        rows = [r for r in rows if r.get("store_id") == store_id]
    products = {p["id"]: p for p in repo.read("Product", tc)}
    items = []
    for ne in rows[:20]:
        prod = products.get(ne.get("product_id"), {})
        tier = ne.get("discount_tier", "T3")
        items.append({
            **ne, "product_name": prod.get("name", ""),
            "discount_percent": calculate_discount(tier),
        })
    return _wrap({"type": "near_expiry_list", "total": len(rows), "items": items},
                 f"查询到 {len(rows)} 条临期商品。")


TOOLS = [query_near_expiry]
