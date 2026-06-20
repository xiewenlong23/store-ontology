"""clearance vertical 专属工具。

从内核 ontology/tools.py 下沉而来（见 docs/manual/01 Batch 2）：
query_near_expiry 是 clearance 领域专属（读 NearExpiryProduct + 算折扣），
不属于通用内核。vertical 工具复用内核的 _get_repo 装配，但不污染内核。
"""
from typing import Optional

from langchain_core.tools import tool

from ontology.tools import _get_repo, _wrap
from business.discount import calculate_discount


@tool
def query_near_expiry(store_id: Optional[str] = None,
                      tenant_id: str = "tenant_default") -> str:
    """查询临期商品列表（折扣来自单一事实源 calculate_discount）。"""
    repo = _get_repo(tenant_id, vertical="clearance")
    rows = repo.read("NearExpiryProduct", tenant_id)
    if store_id:
        rows = [r for r in rows if r.get("store_id") == store_id]
    products = {p["id"]: p for p in repo.read("Product", tenant_id)}
    items = []
    for ne in rows[:20]:
        prod = products.get(ne.get("product_id"), {})
        tier = ne.get("discount_tier", "T3")
        items.append({
            **ne, "product_name": prod.get("name", ""),
            "discount_percent": calculate_discount(tier),  # 单一事实源
        })
    return _wrap({"type": "near_expiry_list", "total": len(rows), "items": items},
                 f"查询到 {len(rows)} 条临期商品。")


# vertical 工具清单：main.py 聚合时 import 取这个列表
TOOLS = [query_near_expiry]
