"""equipment_repair vertical 专属工具。

复用内核装配 _get_repo，但下沉到 vertical 包，不污染内核。
无折扣概念（证明内核改造后不依赖 business.discount）。
"""
from typing import Optional

from langchain_core.tools import tool

from agent.tools import _get_repo, _wrap


@tool
def query_repair_tickets(store_id: Optional[str] = None,
                         status: Optional[str] = None,
                         tenant_id: str = "tenant_default") -> str:
    """查询维修工单列表（可按门店/状态过滤）。"""
    repo = _get_repo(tenant_id, vertical="equipment_repair")
    rows = repo.read("RepairTicket", tenant_id)
    if store_id:
        rows = [r for r in rows if r.get("store_id") == store_id]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return _wrap({"type": "repair_ticket_list", "total": len(rows), "items": rows[:20]},
                 f"查询到 {len(rows)} 条维修工单。")


TOOLS = [query_repair_tickets]
