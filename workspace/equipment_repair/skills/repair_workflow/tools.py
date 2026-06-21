"""equipment_repair 行业包 / repair 价值链流程的专属工具。

复用内核装配 _get_repo，按 workspace 过滤。无折扣概念（证明内核不依赖任何行业包符号）。
"""
from typing import Optional

from langchain_core.tools import tool

from agent.tools import shared as _tools_mod
from agent.tools import _wrap


@tool
def query_repair_tickets(store_id: Optional[str] = None,
                         status: Optional[str] = None,
                         workspace_name: str = "customer_default",
                         org_unit_id: str = "*") -> str:
    """查询维修工单列表（可按门店/状态过滤）。"""
    from engine.tenant import TenantContext
    tc = TenantContext(workspace_name=workspace_name, org_unit_id=org_unit_id)
    repo = _tools_mod._get_repo(tc)  # 延迟引用，支持 monkeypatch
    rows = repo.read("RepairTicket", tc)
    if store_id:
        rows = [r for r in rows if r.get("store_id") == store_id]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return _wrap({"type": "repair_ticket_list", "total": len(rows), "items": rows[:20]},
                 f"查询到 {len(rows)} 条维修工单。")


TOOLS = [query_repair_tickets]
