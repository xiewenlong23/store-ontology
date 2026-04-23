from app.models import Staff, StaffRole, StaffStatus
from app.services.data import get_data_service
import uuid
from datetime import date
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def _load_staff() -> list[dict]:
    return get_data_service().load_all_staff()


def _save_staff(staff_list: list[dict]) -> None:
    get_data_service().save_staff(staff_list)


def list_staff(store_id: Optional[str] = None, role: Optional[StaffRole] = None) -> list[Staff]:
    staff_list = _load_staff()
    if store_id:
        staff_list = [s for s in staff_list if s.get("store_id") == store_id]
    if role:
        staff_list = [s for s in staff_list if s.get("role") == role.value]
    return [Staff(**s) for s in staff_list]


def get_staff(staff_id: str) -> Optional[Staff]:
    staff_list = _load_staff()
    for s in staff_list:
        if s.get("staff_id") == staff_id:
            return Staff(**s)
    return None


def create_staff(staff: Staff) -> Staff:
    staff_list = _load_staff()
    # 检查工号是否重复
    for s in staff_list:
        if s.get("staff_code") == staff.staff_code:
            raise ValueError(f"员工工号 {staff.staff_code} 已存在")
    staff_dict = staff.model_dump()
    staff_dict["staff_id"] = staff_dict.get("staff_id") or str(uuid.uuid4())
    staff_list.append(staff_dict)
    _save_staff(staff_list)
    logger.info(f"[Staff] Created: {staff.staff_name} ({staff.staff_code})")
    return Staff(**staff_dict)


def update_staff(staff_id: str, updates: dict) -> Optional[Staff]:
    staff_list = _load_staff()
    for i, s in enumerate(staff_list):
        if s.get("staff_id") == staff_id:
            staff_list[i].update(updates)
            _save_staff(staff_list)
            logger.info(f"[Staff] Updated: {staff_id}")
            return Staff(**staff_list[i])
    return None


def delete_staff(staff_id: str) -> bool:
    staff_list = _load_staff()
    for i, s in enumerate(staff_list):
        if s.get("staff_id") == staff_id:
            staff_list.pop(i)
            _save_staff(staff_list)
            logger.info(f"[Staff] Deleted: {staff_id}")
            return True
    return False


def get_staff_tasks(staff_id: str) -> list[dict]:
    """获取员工被分配的所有任务"""
    from app.services.data import get_data_service
    tasks = get_data_service().load_all_tasks()
    return [t for t in tasks if t.get("assigned_to") == staff_id or t.get("handled_by") == staff_id]