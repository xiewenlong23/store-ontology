"""本体模型定义 - Pydantic Schemas"""

from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ============ Enums ============

class EmployeeRole(str, Enum):
    CLERK = "clerk"       # 店员
    MANAGER = "manager"    # 店长
    ADMIN = "admin"        # 总部


class DiscountTier(str, Enum):
    T1 = "T1"  # 即将过期，严峻折扣
    T2 = "T2"  # 中期临期，适中折扣
    T3 = "T3"  # 初期临期，轻微折扣


class ProductStatus(str, Enum):
    NORMAL = "normal"           # 正常
    LOW_STOCK = "low_stock"     # 低库存
    EXPIRING = "expiring"       # 临期
    EXPIRED = "expired"         # 已过期


class TaskStatus(str, Enum):
    PENDING = "pending"         # 待执行
    EXECUTING = "executing"    # 执行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============ Object Types ============

class Region(BaseModel):
    """区域 Object Type"""
    id: str = Field(..., description="区域唯一标识")
    name: str = Field(..., description="区域名称")
    code: str = Field(..., description="区域编码")


class Store(BaseModel):
    """门店 Object Type"""
    id: str = Field(..., description="门店唯一标识")
    name: str = Field(..., description="门店名称")
    region_id: str = Field(..., description="所属区域")
    address: str = Field(..., description="门店地址")
    manager_id: str = Field(..., description="店长ID")
    created_at: datetime = Field(default_factory=datetime.now)


class Employee(BaseModel):
    """员工 Object Type"""
    id: str = Field(..., description="员工唯一标识")
    name: str = Field(..., description="员工姓名")
    store_id: str = Field(..., description="所属门店")
    role: EmployeeRole = Field(..., description="角色")
    phone: str = Field(..., description="联系电话")


class Product(BaseModel):
    """商品 Object Type"""
    id: str = Field(..., description="商品唯一标识")
    name: str = Field(..., description="商品名称")
    category: str = Field(..., description="商品类别")
    brand: str = Field(..., description="品牌")
    unit: str = Field(..., description="单位")
    cost_price: float = Field(..., description="成本价")
    retail_price: float = Field(..., description="零售价")


class NearExpiryProduct(BaseModel):
    """临期商品 Object Type"""
    id: str = Field(..., description="临期商品实例ID")
    product_id: str = Field(..., description="关联商品")
    store_id: str = Field(..., description="所属门店")
    batch_no: str = Field(..., description="批次号")
    production_date: date = Field(..., description="生产日期")
    expiry_date: date = Field(..., description="过期日期")
    stock_quantity: int = Field(..., description="库存数量")
    days_left: int = Field(0, description="剩余天数")
    discount_tier: DiscountTier = Field(..., description="折扣层级")
    status: ProductStatus = Field(..., description="状态")

    def calc_days_left(self) -> int:
        """计算剩余天数"""
        today = date.today()
        delta = self.expiry_date - today
        return delta.days


class DiscountRule(BaseModel):
    """折扣规则 - Action Type 的业务规则"""
    id: str = Field(..., description="规则ID")
    tier: DiscountTier = Field(..., description="层级")
    days_min: int = Field(..., description="最小天数")
    days_max: int = Field(..., description="最大天数")
    discount_rate: float = Field(..., ge=0, le=1, description="折扣率(0-1)")
    description: str = Field(..., description="规则描述")


# ============ Action Types & Tasks ============

class ClearanceParams(BaseModel):
    """Clearance Action - 输入参数"""
    near_expiry_product_id: str = Field(..., description="临期商品ID")
    quantity: int = Field(..., gt=0, description="出清数量")
    assignee_id: str = Field(..., description="负责人ID")
    target_discount: Optional[float] = Field(None, ge=0, le=1, description="目标折扣")
    notes: Optional[str] = Field(None, description="备注")


class CompleteClearanceParams(BaseModel):
    """CompleteClearance Action - 输入参数"""
    task_id: str = Field(..., description="任务ID")
    actual_discount: float = Field(..., ge=0, le=1, description="实际折扣")
    notes: Optional[str] = Field(None, description="备注")


class ClearanceTask(BaseModel):
    """ClearanceTask = Action Instance (任务)"""
    id: str = Field(..., description="任务ID")
    action_type: str = Field(default="clearance", description="动作类型")
    near_expiry_product_id: str = Field(..., description="关联临期商品")
    store_id: str = Field(..., description="所属门店")
    assignee_id: str = Field(..., description="负责人")
    input_params: ClearanceParams = Field(..., description="Action输入参数")
    output_result: dict = Field(default_factory=dict, description="Action输出结果")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="状态")
    actual_discount: Optional[float] = Field(None, description="实际折扣")
    quantity: int = Field(..., description="出清数量")
    priority: Priority = Field(default=Priority.MEDIUM, description="优先级")
    notes: Optional[str] = Field(None, description="备注")
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============ Link Types (关系) ============

class LinkTypes:
    """Link Type 定义常量"""
    LOCATED_IN = "located_in"                    # Store -> Region
    HAS_NEAR_EXPIRY_PRODUCT = "has_near_expiry_product"  # Store -> NearExpiryProduct
    IS_INSTANCE_OF = "is_instance_of"             # NearExpiryProduct -> Product
    BELONGS_TO = "belongs_to"                     # Employee -> Store
    MANAGES = "manages"                          # Employee -> Store
    SUBJECT_TO = "subject_to"                    # NearExpiryProduct -> DiscountRule
    ASSIGNED_TO = "assigned_to"                  # ClearanceTask -> Employee
    CREATED_FOR = "created_for"                  # ClearanceTask -> NearExpiryProduct
