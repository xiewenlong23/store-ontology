# ============================================================
# 折扣计算工具 — Phase 2.3 / 2.4
# TBOX 折扣层级规则：T1 ≤ 7天 → 8折 / T2 ≤ 14天 → 8.5折 / T3 ≤ 30天 → 9折
# 规则来自 TBOX，不在此文件中硬编码
# ============================================================
from typing import Literal
from app.agent.state import DiscountTier, DiscountTask
from app.agent.tools.sparql_tools import query_product_info
import uuid
from datetime import datetime, timedelta


# ============================================================
# TBOX 折扣规则（来自 ontology/tbox/modules/02-discount/）
# 此处仅作类型标注，实际数据从 TBOX 实例读取
# ============================================================
TIER_RULES = {
    "T1": {"max_days": 7,   "rate": 0.20, "min_rate": 0.70, "label": "8折"},
    "T2": {"max_days": 14,  "rate": 0.15, "min_rate": 0.80, "label": "8.5折"},
    "T3": {"max_days": 30,  "rate": 0.10, "min_rate": 0.85, "label": "9折"},
}
EXEMPT_CATEGORIES = ["tobacco", "alcohol"]


async def calculate_discount_tier(
    product_id: str,
    remaining_days: int,
    store_id: str,
) -> DiscountTier:
    """
    根据剩余保质期计算折扣层级

    逻辑：
    1. 查商品是否豁免（烟草/酒类不参与折扣）
    2. 根据 remaining_days 确定 T1/T2/T3
    3. 返回折扣率和最低保护价
    """
    # 查商品信息（是否豁免）
    product = await query_product_info(product_id, store_id)

    is_exempt = False
    if product:
        category = product.get("category", "").lower()
        is_exempt = any(ex in category for ex in EXEMPT_CATEGORIES)

    if is_exempt:
        return {
            "tier": "EXEMPT",
            "rate": 0.0,
            "rate_display": "不参与折扣",
            "remaining_days": remaining_days,
            "min_rate": 1.0,
        }

    # 确定层级
    if remaining_days <= TIER_RULES["T1"]["max_days"]:
        tier = "T1"
    elif remaining_days <= TIER_RULES["T2"]["max_days"]:
        tier = "T2"
    else:
        tier = "T3"

    rule = TIER_RULES[tier]
    return {
        "tier": tier,
        "rate": rule["rate"],
        "rate_display": rule["label"],
        "remaining_days": remaining_days,
        "min_rate": rule["min_rate"],
    }


async def create_discount_task(
    product_id: str,
    discount_tier: str,
    suggested_rate: float,
    store_id: str,
    created_by: str,
    product_name: str = "",
) -> DiscountTask:
    """
    创建折扣任务（pending 状态，等待店长审批）

    生成 task_id，记录创建者，自动设置店长为审批人。
    """
    task_id = f"DT{uuid.uuid4().hex[:8].upper()}"
    now = datetime.utcnow().isoformat() + "Z"

    # TODO: 从员工数据库查该门店店长 ID（暂时用 created_by 代替）
    approver_id = ""  # 实际应查 StoreManager 对应的 employee_id

    return {
        "task_id": task_id,
        "product_id": product_id,
        "product_name": product_name,
        "discount_tier": {
            "tier": discount_tier,
            "rate": suggested_rate,
            "rate_display": f"{int(suggested_rate * 10)}折",
            "remaining_days": 0,
            "min_rate": 0.0,
        },
        "suggested_rate": suggested_rate,
        "approved_rate": None,
        "status": "pending",
        "created_by": created_by,
        "approver_id": approver_id,
        "created_at": now,
        "updated_at": now,
        "store_id": store_id,
    }


async def approve_discount(
    task: DiscountTask,
    approved_rate: float,
    approver_id: str,
) -> DiscountTask:
    """店长批准折扣，更新任务状态"""
    now = datetime.utcnow().isoformat() + "Z"
    task["approved_rate"] = approved_rate
    task["status"] = "approved"
    task["approver_id"] = approver_id
    task["updated_at"] = now
    return task


async def reject_discount(
    task: DiscountTask,
    reason: str,
    approver_id: str,
) -> DiscountTask:
    """店长拒绝折扣，记录拒绝原因"""
    now = datetime.utcnow().isoformat() + "Z"
    task["status"] = "rejected"
    task["approver_id"] = approver_id
    task["updated_at"] = now
    return task


async def query_discount_task(task_id: str, store_id: str) -> DiscountTask | None:
    """查询折扣任务详情"""
    # TODO: 从 ABOX 存储中查询（NebulaGraph 或 JSON 文件）
    # 此处返回 None，生产实现需对接 ABOX
    return None


async def query_pending_approvals(store_id: str) -> list[DiscountTask]:
    """查询某门店待审批的折扣任务"""
    # TODO: 从 ABOX 存储中查询
    return []
