from fastapi import APIRouter, HTTPException
from app.models import ReductionTask, TaskStatus
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import json, uuid

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent / "data"
TASKS_FILE = DATA_DIR / "tasks.json"

def load_tasks():
    with open(TASKS_FILE) as f:
        return json.load(f)

def save_tasks(tasks):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2, default=str)

@router.get("/", response_model=list[ReductionTask])
def list_tasks(store_id: str = None, status: TaskStatus = None):
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


class ChatIntentRequest(BaseModel):
    message: str

@router.post("/chat/interpret")
def interpret_chat(req: ChatIntentRequest):
    msg = req.message
    if "查询" in msg or "有哪些" in msg:
        intent = "query_status"
    elif "创建" in msg or "帮我" in msg:
        intent = "create_task"
    elif "售罄率" in msg or "结果" in msg:
        intent = "report_result"
    else:
        intent = "unknown"
    return {"intent": intent, "message": msg}
