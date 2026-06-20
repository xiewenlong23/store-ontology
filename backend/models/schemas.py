"""本体模型定义 - Pydantic Schemas（对齐 store.ttl，见建模规范 §7.3）。"""

from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ============ Enums ============

class EmployeeRole(str, Enum):
    CLERK = "clerk"
    MANAGER = "manager"
    ADMIN = "admin"


class DiscountTier(str, Enum):
    T1 = "T1"   # 即将过期
    T2 = "T2"   # 中期临期
    T3 = "T3"   # 初期临期


class NearExpiryProductStatus(str, Enum):
    EXPIRING = "expiring"
    CLEARANCE = "clearance"
    SOLD_OUT = "sold_out"
    EXPIRED = "expired"
    SCRAPPED = "scrapped"


class TaskStatus(str, Enum):
    CREATED = "created"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    SCRAPPED = "scrapped"


class TaskType(str, Enum):
    """clearance vertical 的任务类型。

    注：transfer(调拨)/restock(补货) 是规划中的后续业务流程，当前未建模
    （无 Action/TTL 流程）。按建模规范原则4（OCP），未实现的不声明，
    待实际建模时再加回。避免僵尸词汇误导。
    """
    CLEARANCE = "clearance"


class LossReportStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============ Object Types ============

class Region(BaseModel):
    id: str
    name: str
    code: str


class Store(BaseModel):
    id: str
    name: str
    region_id: str
    address: str
    manager_id: str
    created_at: datetime = Field(default_factory=datetime.now)


class Employee(BaseModel):
    id: str
    name: str
    store_id: str
    role: EmployeeRole
    phone: str


class Product(BaseModel):
    id: str
    name: str
    category: str
    brand: str
    unit: str
    cost_price: float           # 单位：元
    retail_price: float         # 单位：元


class NearExpiryProduct(BaseModel):
    id: str
    product_id: str
    store_id: str
    batch_no: str
    production_date: date
    expiry_date: date
    stock_quantity: int         # 单位：件
    days_left: int              # 单位：天
    discount_tier: DiscountTier
    status: NearExpiryProductStatus

    def calc_days_left(self) -> int:
        return (self.expiry_date - date.today()).days


class Task(BaseModel):
    """出清任务（受治理工作流载体）。"""
    id: str
    task_type: TaskType
    target_id: str
    store_id: str
    assignee_id: str
    status: TaskStatus = TaskStatus.CREATED
    discount_percent: int = Field(0, ge=0, le=100, description="减扣百分比(0-100)，50=五折")
    planned_quantity: int = Field(0, ge=0, description="件")
    sold_quantity: int = Field(0, ge=0, description="件")
    params_json: dict = Field(default_factory=dict)
    result_json: dict = Field(default_factory=dict)
    priority: Priority = Priority.MEDIUM
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class LossReport(BaseModel):
    """报损单。"""
    id: str
    task_id: str
    target_id: str
    loss_quantity: int = Field(..., ge=0, description="件")
    loss_value: float = Field(..., ge=0, description="元")
    loss_reason: str
    status: LossReportStatus = LossReportStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
