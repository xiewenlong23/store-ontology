from typing import Optional
from app.models import Inventory, InventoryStatus, InventoryEvent, InventoryEventType
from app.services.data import get_data_service
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


def list_inventory(store_id: str = None, product_id: str = None, status: InventoryStatus = None) -> list[Inventory]:
    inv_list = get_data_service().load_inventory(store_id=store_id, product_id=product_id)
    if status:
        inv_list = [i for i in inv_list if i.get("status") == status.value]
    return [Inventory(**i) for i in inv_list]


def get_inventory(inventory_id: str) -> Optional[Inventory]:
    all_inv = get_data_service().load_all_inventory()
    for i in all_inv:
        if i.get("inventory_id") == inventory_id:
            return Inventory(**i)
    return None


def create_inventory(inv: Inventory) -> Inventory:
    inv_list = get_data_service().load_all_inventory()
    inv_dict = inv.model_dump()
    inv_dict["inventory_id"] = inv_dict.get("inventory_id") or str(uuid.uuid4())
    inv_list.append(inv_dict)
    get_data_service().save_inventory(inv_list)
    logger.info(f"[Inventory] Created: {inv_dict['inventory_id']} ({inv_dict.get('product_id')})")
    return Inventory(**inv_dict)


def update_inventory(inventory_id: str, updates: dict) -> Optional[Inventory]:
    inv_list = get_data_service().load_all_inventory()
    for i, inv in enumerate(inv_list):
        if inv.get("inventory_id") == inventory_id:
            inv_list[i].update(updates)
            get_data_service().save_inventory(inv_list)
            logger.info(f"[Inventory] Updated: {inventory_id}")
            return Inventory(**inv_list[i])
    return None


def delete_inventory(inventory_id: str) -> bool:
    inv_list = get_data_service().load_all_inventory()
    for i, inv in enumerate(inv_list):
        if inv.get("inventory_id") == inventory_id:
            inv_list.pop(i)
            get_data_service().save_inventory(inv_list)
            logger.info(f"[Inventory] Deleted: {inventory_id}")
            return True
    return False


def get_low_stock(store_id: str = None) -> list[Inventory]:
    """库存 ≤ reorder_point 的商品"""
    inv_list = get_data_service().load_inventory(store_id=store_id)
    low_stock = []
    for inv in inv_list:
        if inv.get("quantity", 0) <= inv.get("reorder_point", 0):
            low_stock.append(Inventory(**inv))
    return low_stock


def get_near_expiry_inventory(store_id: str = None) -> list[Inventory]:
    """临期库存（status = near_expiry）"""
    return list_inventory(store_id=store_id, status=InventoryStatus.NEAR_EXPIRY)


def create_inventory_event(event: InventoryEvent) -> InventoryEvent:
    """创建库存事件并更新关联库存的状态"""
    all_inv = get_data_service().load_all_inventory()

    # 更新库存状态
    for i, inv in enumerate(all_inv):
        if inv.get("inventory_id") == event.inventory_id:
            # 根据事件类型更新库存状态
            if event.event_type == InventoryEventType.NEAR_EXPIRY:
                all_inv[i]["status"] = InventoryStatus.NEAR_EXPIRY.value
            elif event.event_type == InventoryEventType.OUT_OF_STOCK:
                all_inv[i]["status"] = InventoryStatus.OUT_OF_STOCK.value
            elif event.event_type == InventoryEventType.RESTOCK:
                all_inv[i]["status"] = InventoryStatus.NORMAL.value
            # 更新库存数量
            if event.quantity_after >= 0:
                all_inv[i]["quantity"] = event.quantity_after
            get_data_service().save_inventory(all_inv)
            break

    # 保存事件（存在 events.json）
    events = _load_events()
    event_dict = event.model_dump()
    event_dict["event_id"] = event_dict.get("event_id") or str(uuid.uuid4())
    events.append(event_dict)
    _save_events(events)
    logger.info(f"[InventoryEvent] Created: {event_dict['event_id']} ({event.event_type.value})")
    return InventoryEvent(**event_dict)


def list_inventory_events(
    inventory_id: str = None,
    event_type: InventoryEventType = None,
    store_id: str = None,
) -> list[InventoryEvent]:
    events = _load_events()
    if inventory_id:
        events = [e for e in events if e.get("inventory_id") == inventory_id]
    if event_type:
        events = [e for e in events if e.get("event_type") == event_type.value]
    if store_id:
        # 需要关联 inventory 来过滤 store_id
        inv_map = {i["inventory_id"]: i.get("store_id") for i in get_data_service().load_all_inventory()}
        events = [e for e in events if inv_map.get(e.get("inventory_id")) == store_id]
    return [InventoryEvent(**e) for e in events]


def check_product_exemption_from_json(product: dict) -> Optional[dict]:
    """
    基于商品属性（来自 JSON）判断豁免类型。

    Args:
        product: 商品字典，应包含 is_imported, is_organic, is_promoted, arrival_days 等字段

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
    # 通用豁免：exemption_type 字段直接标识
    if product.get("exemption_type"):
        return {"exemption_type": product["exemption_type"], "exemption_reason": product.get("exemption_reason", ""), "rule_source": "headquarters"}
    return None


# ── 内部方法 ───────────────────────────────────────────────────

def _load_events() -> list[dict]:
    from pathlib import Path
    events_file = Path(__file__).parent.parent.parent / "data" / "events.json"
    try:
        import json
        with open(events_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_events(events: list[dict]) -> None:
    from pathlib import Path
    events_file = Path(__file__).parent.parent.parent / "data" / "events.json"
    import json
    with open(events_file, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)