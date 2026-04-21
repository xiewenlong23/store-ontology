from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(tags=["pos"])


class POSSaleRequest(BaseModel):
    task_id: str
    product_id: str
    original_stock: int
    discount_rate: float
    days_elapsed: int = 1


class POSDailySalesRequest(BaseModel):
    task_id: str
    product_id: str
    original_stock: int
    discount_rate: float
    days_elapsed: int


@router.post("/sale/record")
def record_sale(req: POSSaleRequest):
    """
    模拟POS系统回写单次销售记录

    计算 sell_through_rate 并发送 POS_SALE_RECORDED 事件
    """
    from app.services.pos_simulator import get_pos_simulator

    pos = get_pos_simulator()
    record = pos.record_sale(
        task_id=req.task_id,
        product_id=req.product_id,
        original_stock=req.original_stock,
        discount_rate=req.discount_rate,
        days_elapsed=req.days_elapsed,
    )
    return record


@router.post("/sale/simulate-daily")
def simulate_daily_sales(req: POSDailySalesRequest):
    """
    模拟多天POS销售（用于批量处理和任务复核）

    返回每天的销售明细和最终的 sell_through_rate
    """
    from app.services.pos_simulator import get_pos_simulator

    pos = get_pos_simulator()
    result = pos.simulate_daily_sales(
        task_id=req.task_id,
        product_id=req.product_id,
        original_stock=req.original_stock,
        discount_rate=req.discount_rate,
        days_elapsed=req.days_elapsed,
    )
    return result


@router.get("/sales/history")
def get_sales_history(task_id: Optional[str] = None, limit: int = 100):
    """
    查询POS销售历史

    可按 task_id 过滤
    """
    from app.services.pos_simulator import load_pos_sales

    sales = load_pos_sales()
    if task_id:
        sales = [s for s in sales if s.get("task_id") == task_id]
    return {
        "total": len(sales),
        "records": sales[-limit:],
    }


@router.get("/events")
def get_pos_events(limit: int = 100):
    """查询POS相关事件历史"""
    from app.services.event_system import get_event_bus, EventType

    event_bus = get_event_bus()
    history = event_bus.get_history(event_type=EventType.POS_SALE_RECORDED, limit=limit)
    return {
        "total": len(history),
        "events": history,
    }
