from fastapi import APIRouter, HTTPException
from app.models import ReductionTask, TaskStatus, RiskLevel, ExemptionType
from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional
from pathlib import Path
import json
import fcntl
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / "data"
TASKS_FILE = DATA_DIR / "tasks.json"

def load_tasks():
    try:
        with open(TASKS_FILE) as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except FileNotFoundError:
        logger.warning(f"Tasks file not found: {TASKS_FILE}, returning empty list")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in tasks file: {TASKS_FILE}: {e}")
        return []

def save_tasks(tasks):
    try:
        with open(TASKS_FILE, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(tasks, f, indent=2, default=str)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError as e:
        logger.error(f"Failed to save tasks to {TASKS_FILE}: {e}")
        raise

@router.get("/", response_model=list[ReductionTask])
def list_tasks(store_id: Optional[str] = None, status: Optional[TaskStatus] = None):
    tasks = load_tasks()
    if store_id:
        tasks = [t for t in tasks if t["store_id"] == store_id]
    if status:
        tasks = [t for t in tasks if t["status"] == status.value]
    return tasks

@router.post("/", response_model=ReductionTask)
def create_task(task: ReductionTask):
    tasks = load_tasks()
    task_dict = task.model_dump()
    task_dict["task_id"] = str(uuid.uuid4())
    task_dict["created_at"] = datetime.now().isoformat()
    tasks.append(task_dict)
    save_tasks(tasks)
    return task_dict

@router.get("/{task_id}", response_model=ReductionTask)
def get_task(task_id: str):
    tasks = load_tasks()
    for t in tasks:
        if t["task_id"] == task_id:
            return t
    raise HTTPException(status_code=404, detail="Task not found")

@router.patch("/{task_id}/status")
def update_task_status(task_id: str, status: TaskStatus):
    tasks = load_tasks()
    for t in tasks:
        if t["task_id"] == task_id:
            t["status"] = status.value
            save_tasks(tasks)
            return t
    raise HTTPException(status_code=404, detail="Task not found")

@router.patch("/{task_id}/complete")
def complete_task(task_id: str, sold_qty: int):
    """废弃：保留兼容性，请使用 /review 端点"""
    tasks = load_tasks()
    for t in tasks:
        if t["task_id"] == task_id:
            t["status"] = TaskStatus.COMPLETED.value
            original_stock = t.get("original_stock", 0)
            if original_stock == 0:
                t["sell_through_rate"] = 0.0
            else:
                t["sell_through_rate"] = sold_qty / original_stock
            save_tasks(tasks)
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
def confirm_task(task_id: str, req: ConfirmRequest):
    """
    确认任务：Pending → Confirmed

    店长审批或AI自动确认后执行此端点。
    """
    tasks = load_tasks()
    _, task = _get_task(tasks, task_id)

    if TaskStatus(task["status"]) != TaskStatus.PENDING:
        raise HTTPException(status_code=400, detail="只有Pending状态的任务可以确认")

    task["status"] = TaskStatus.CONFIRMED.value
    task["confirmed_discount_rate"] = req.confirmed_discount_rate
    task["confirmed_by"] = req.confirmed_by
    task["confirmed_at"] = datetime.now().isoformat()
    if req.notes:
        task["confirmed_notes"] = req.notes

    save_tasks(tasks)

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
def execute_task(task_id: str, req: ExecuteRequest):
    """
    执行任务：Confirmed → Executed

    员工完成IF枪扫描和价签打印后执行此端点。
    """
    tasks = load_tasks()
    _, task = _get_task(tasks, task_id)

    if TaskStatus(task["status"]) != TaskStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail="只有Confirmed状态的任务可以执行")

    task["status"] = TaskStatus.EXECUTED.value
    task["executed_by"] = req.executed_by
    task["executed_at"] = datetime.now().isoformat()
    task["scan_barcode"] = req.scan_barcode
    task["price_label_printed"] = req.price_label_printed
    if req.executed_discount_rate is not None:
        task["executed_discount_rate"] = req.executed_discount_rate

    save_tasks(tasks)

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
def review_task(task_id: str, req: ReviewRequest):
    """
    复核任务：Executed → Reviewed/Completed

    店长复核售罄率，确认任务闭环。
    """
    tasks = load_tasks()
    _, task = _get_task(tasks, task_id)

    if TaskStatus(task["status"]) != TaskStatus.EXECUTED.value:
        raise HTTPException(status_code=400, detail="只有Executed状态的任务可以复核")

    task["status"] = TaskStatus.REVIEWED.value
    task["reviewed_by"] = req.reviewed_by
    task["reviewed_at"] = datetime.now().isoformat()
    task["sell_through_rate"] = req.sell_through_rate
    if req.review_notes:
        task["review_notes"] = req.review_notes

    # 如果不需要整改，直接标记为完成
    if not req.requires_rectification:
        task["status"] = TaskStatus.COMPLETED.value

    save_tasks(tasks)

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
