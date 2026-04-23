from fastapi import APIRouter, HTTPException
from typing import Optional

from app.models import Inventory, InventoryStatus, InventoryEvent, InventoryEventType
from app.services import inventory_service
from app.services.context import get_context

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/", response_model=list[Inventory])
def list_inventory(
    store_id: Optional[str] = None,
    product_id: Optional[str] = None,
    status: Optional[InventoryStatus] = None,
):
    """库存列表（支持门店/商品/状态过滤）"""
    # Clerk 强制只看自己门店
    ctx = get_context()
    if ctx.user_role == "clerk" and ctx.store_id:
        store_id = ctx.store_id
    return inventory_service.list_inventory(store_id=store_id, product_id=product_id, status=status)


@router.get("/low-stock", response_model=list[Inventory])
def low_stock(store_id: Optional[str] = None):
    """缺货警告：库存 ≤ 补货点"""
    ctx = get_context()
    if ctx.user_role == "clerk" and ctx.store_id:
        store_id = ctx.store_id
    return inventory_service.get_low_stock(store_id=store_id)


@router.get("/near-expiry", response_model=list[Inventory])
def near_expiry(store_id: Optional[str] = None):
    """临期库存：status = near_expiry"""
    ctx = get_context()
    if ctx.user_role == "clerk" and ctx.store_id:
        store_id = ctx.store_id
    return inventory_service.get_near_expiry_inventory(store_id=store_id)


@router.get("/{inventory_id}", response_model=Inventory)
def get_inventory(inventory_id: str):
    inv = inventory_service.get_inventory(inventory_id)
    if not inv:
        raise HTTPException(status_code=404, detail="库存记录不存在")
    ctx = get_context()
    if ctx.user_role == "clerk" and ctx.store_id and inv.store_id != ctx.store_id:
        raise HTTPException(status_code=403, detail="无权查看该库存")
    return inv


@router.post("/", response_model=Inventory)
def create_inventory(inv: Inventory):
    return inventory_service.create_inventory(inv)


@router.patch("/{inventory_id}", response_model=Inventory)
def update_inventory(inventory_id: str, updates: dict):
    inv = inventory_service.update_inventory(inventory_id, updates)
    if not inv:
        raise HTTPException(status_code=404, detail="库存记录不存在")
    return inv


@router.delete("/{inventory_id}")
def delete_inventory(inventory_id: str):
    if not inventory_service.delete_inventory(inventory_id):
        raise HTTPException(status_code=404, detail="库存记录不存在")
    return {"success": True}


# ── InventoryEvent 端点 ────────────────────────────────────────

@router.get("/events/", response_model=list[InventoryEvent])
def list_events(
    inventory_id: Optional[str] = None,
    event_type: Optional[InventoryEventType] = None,
    store_id: Optional[str] = None,
):
    """库存事件列表"""
    return inventory_service.list_inventory_events(
        inventory_id=inventory_id,
        event_type=event_type,
        store_id=store_id,
    )


@router.post("/events/", response_model=InventoryEvent)
def create_event(event: InventoryEvent):
    """创建库存事件（如临期检测/缺货/到货），同时更新库存状态"""
    return inventory_service.create_inventory_event(event)