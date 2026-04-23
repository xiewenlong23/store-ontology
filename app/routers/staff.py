from fastapi import APIRouter, HTTPException
from typing import Optional

from app.models import Staff, StaffRole, StaffStatus
from app.services import staff_service
from app.services.context import get_context

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/", response_model=list[Staff])
def list_staff(store_id: Optional[str] = None, role: Optional[StaffRole] = None):
    """员工列表（支持门店/角色过滤）"""
    return staff_service.list_staff(store_id=store_id, role=role)


@router.get("/{staff_id}", response_model=Staff)
def get_staff(staff_id: str):
    staff = staff_service.get_staff(staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="员工不存在")
    return staff


@router.post("/", response_model=Staff)
def create_staff(staff: Staff):
    try:
        return staff_service.create_staff(staff)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{staff_id}", response_model=Staff)
def update_staff(staff_id: str, updates: dict):
    staff = staff_service.update_staff(staff_id, updates)
    if not staff:
        raise HTTPException(status_code=404, detail="员工不存在")
    return staff


@router.delete("/{staff_id}")
def delete_staff(staff_id: str):
    if not staff_service.delete_staff(staff_id):
        raise HTTPException(status_code=404, detail="员工不存在")
    return {"success": True}


@router.get("/{staff_id}/tasks")
def staff_tasks(staff_id: str):
    """获取员工被分配的所有任务"""
    return staff_service.get_staff_tasks(staff_id)