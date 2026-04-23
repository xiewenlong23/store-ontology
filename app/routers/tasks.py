from fastapi import APIRouter, HTTPException
from app.models import ReductionTask, TaskStatus, RiskLevel, ExemptionType
from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional
from app.services.data import get_data_service
from app.services.context import get_context
from app.middleware.permission import require_role
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=list[ReductionTask])
def list_tasks(store_id: Optional[str] = None, status: Optional[TaskStatus] = None):
    # Clerk 强制只能看自己门店
    ctx = get_context()
    if ctx.user_role == "clerk" and ctx.store_id:
        store_id = ctx.store_id
    tasks = get_data_service().load_tasks(store_id)
    if store_id:
        tasks = [t for t in tasks if t["store_id"] == store_id]
    if status:
        tasks = [t for t in tasks if t["status"] == status.value]
    return tasks

@router.post("/", response_model=ReductionTask)
def create_task(task: ReductionTask):
    tasks = get_data_service().load_all_tasks()
    task_dict = task.model_dump()
    task_dict["task_id"] = str(uuid.uuid4())
    task_dict["created_at"] = datetime.now().isoformat()
    tasks.append(task_dict)
    get_data_service().save_tasks(tasks)
    return task_dict

@router.get("/{task_id}", response_model=ReductionTask)
def get_task(task_id: str):
    tasks = get_data_service().load_all_tasks()
    for t in tasks:
        if t["task_id"] == task_id:
            ctx = get_context()
            # Clerk 只能查看自己门店的任务
            if ctx.user_role == "clerk" and ctx.store_id and t.get("store_id") != ctx.store_id:
                raise HTTPException(status_code=403, detail="无权查看该任务")
            return t
    raise HTTPException(status_code=404, detail="Task not found")

@router.patch("/{task_id}/status")
def update_task_status(task_id: str, status: TaskStatus):
    tasks = get_data_service().load_all_tasks()
    for t in tasks:
        if t["task_id"] == task_id:
            ctx = get_context()
            if ctx.user_role == "clerk" and ctx.store_id and t.get("store_id") != ctx.store_id:
                raise HTTPException(status_code=403, detail="无权操作该任务")
            t["status"] = status.value
            get_data_service().save_tasks(tasks)
            return t
    raise HTTPException(status_code=404, detail="Task not found")

@router.patch("/{task_id}/complete")
def complete_task(task_id: str, sold_qty: int):
    """废弃：保留兼容性，请使用 /review 端点"""
    tasks = get_data_service().load_all_tasks()
    for t in tasks:
        if t["task_id"] == task_id:
            ctx = get_context()
            if ctx.user_role == "clerk" and ctx.store_id and t.get("store_id") != ctx.store_id:
                raise HTTPException(status_code=403, detail="无权操作该任务")
            t["status"] = TaskStatus.COMPLETED.value
            original_stock = t.get("original_stock", 0)
            if original_stock == 0:
                t["sell_through_rate"] = 0.0
            else:
                t["sell_through_rate"] = sold_qty / original_stock
            get_data_service().save_tasks(tasks)
            return t
    raise HTTPException(status_code=404, detail="Task not found")


class ConfirmRequest(BaseModel):
    confirmed_discount_rate: float
    confirmed_by: str = "AI"
    notes: Optional[str] = None


class ExecuteRequest(BaseModel):
    executed_by: str
    scan_barcode: str
    price_label_printed: bool = True
    executed_discount_rate: Optional[float] = None


class ReviewRequest(BaseModel):
    reviewed_by: str
    sell_through_rate: float
    review_notes: Optional[str] = None
    requires_rectification: bool = False


def _get_task(tasks: list, task_id: str) -> tuple[int, dict]:
    """查找任务，返回(索引, 任务dict)"""
    for i, t in enumerate(tasks):
        if t["task_id"] == task_id:
            return i, t
    raise HTTPException(status_code=404, detail="Task not found")


@router.patch("/{task_id}/confirm")
@require_role("manager", "headquarters")
def confirm_task(task_id: str, req: ConfirmRequest):
    """
    确认任务：Pending → Confirmed

    店长审批或AI自动确认后执行此端点。
    仅 manager/headquarters 可调用。
    """
    tasks = get_data_service().load_all_tasks()
    _, task = _get_task(tasks, task_id)

    if TaskStatus(task["status"]) != TaskStatus.PENDING:
        raise HTTPException(status_code=400, detail="只有Pending状态的任务可以确认")

    ctx = get_context()
    if ctx.user_role == "clerk" and ctx.store_id and task.get("store_id") != ctx.store_id:
        raise HTTPException(status_code=403, detail="无权操作该任务")

    task["status"] = TaskStatus.CONFIRMED.value
    task["confirmed_discount_rate"] = req.confirmed_discount_rate
    task["confirmed_by"] = req.confirmed_by
    task["confirmed_at"] = datetime.now().isoformat()
    if req.notes:
        task["confirmed_notes"] = req.notes

    get_data_service().save_tasks(tasks)

    # 发送事件
    from app.services.event_system import get_event_bus, EventType
    event_bus = get_event_bus()
    event_id = event_bus.emit_task_event(
        event_type=EventType.TASK_CONFIRMED,
        task_id=task_id,
        product_id=task["product_id"],
        from_status=TaskStatus.PENDING.value,
        to_status=TaskStatus.CONFIRMED.value,
    )
    task["trigger_event_id"] = event_id

    return task


@router.patch("/{task_id}/execute")
@require_role("clerk", "manager", "headquarters")
def execute_task(task_id: str, req: ExecuteRequest):
    """
    执行任务：Confirmed → Executed

    员工完成IF枪扫描和价签打印后执行此端点。
    """
    tasks = get_data_service().load_all_tasks()
    _, task = _get_task(tasks, task_id)

    ctx = get_context()
    if ctx.user_role == "clerk" and ctx.store_id and task.get("store_id") != ctx.store_id:
        raise HTTPException(status_code=403, detail="无权操作该任务")

    if TaskStatus(task["status"]) != TaskStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail="只有Confirmed状态的任务可以执行")

    task["status"] = TaskStatus.EXECUTED.value
    task["executed_by"] = req.executed_by
    task["executed_at"] = datetime.now().isoformat()
    task["scan_barcode"] = req.scan_barcode
    task["price_label_printed"] = req.price_label_printed
    if req.executed_discount_rate is not None:
        task["executed_discount_rate"] = req.executed_discount_rate

    get_data_service().save_tasks(tasks)

    # 发送事件
    from app.services.event_system import get_event_bus, EventType
    event_bus = get_event_bus()
    event_id = event_bus.emit_task_event(
        event_type=EventType.TASK_EXECUTED,
        task_id=task_id,
        product_id=task["product_id"],
        from_status=TaskStatus.CONFIRMED.value,
        to_status=TaskStatus.EXECUTED.value,
    )
    task["trigger_event_id"] = event_id

    return task


@router.patch("/{task_id}/review")
@require_role("manager", "headquarters")
def review_task(task_id: str, req: ReviewRequest):
    """
    复核任务：Executed → Reviewed/Completed

    店长复核售罄率，确认任务闭环。
    仅 manager/headquarters 可调用。
    """
    tasks = get_data_service().load_all_tasks()
    _, task = _get_task(tasks, task_id)

    if TaskStatus(task["status"]) != TaskStatus.EXECUTED.value:
        raise HTTPException(status_code=400, detail="只有Executed状态的任务可以复核")

    ctx = get_context()
    if ctx.user_role == "clerk" and ctx.store_id and task.get("store_id") != ctx.store_id:
        raise HTTPException(status_code=403, detail="无权操作该任务")

    task["status"] = TaskStatus.REVIEWED.value
    task["reviewed_by"] = req.reviewed_by
    task["reviewed_at"] = datetime.now().isoformat()
    task["sell_through_rate"] = req.sell_through_rate
    if req.review_notes:
        task["review_notes"] = req.review_notes

    # 如果不需要整改，直接标记为完成
    if not req.requires_rectification:
        task["status"] = TaskStatus.COMPLETED.value

    get_data_service().save_tasks(tasks)

    # 发送事件
    from app.services.event_system import get_event_bus, EventType
    event_bus = get_event_bus()
    event_id = event_bus.emit_task_event(
        event_type=EventType.TASK_REVIEWED,
        task_id=task_id,
        product_id=task["product_id"],
        from_status=TaskStatus.EXECUTED.value,
        to_status=TaskStatus.REVIEWED.value,
    )
    task["trigger_event_id"] = event_id

    return task
