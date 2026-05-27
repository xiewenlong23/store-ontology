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


class ActionType(str, Enum):
    """Action Type 枚举 — 所有可执行操作的类型，在代码中校验。"""
    CLEARANCE = "clearance"
    TRANSFER = "transfer"
    RESTOCK = "restock"


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


# ============ Link Types ============

class LinkTypes:
    """Link Type 定义常量"""
    LOCATED_IN = "located_in"                    # Store -> Region
    HAS_NEAR_EXPIRY_PRODUCT = "has_near_expiry_product"  # Store -> NearExpiryProduct
    IS_INSTANCE_OF = "is_instance_of"             # NearExpiryProduct -> Product
    BELONGS_TO = "belongs_to"                     # Employee -> Store
    MANAGES = "manages"                          # Employee -> Store
    SUBJECT_TO = "subject_to"                    # NearExpiryProduct -> DiscountRule
    HAS_TASK = "has_task"                        # Store -> Task
    CREATED_FOR = "created_for"                  # Task -> NearExpiryProduct


# ============ Action Types ============

class Task(BaseModel):
    """通用任务 Object Type

    Action Type 的执行记录。每个 Task 对应一次操作执行。
    type 字段标识操作类型（clearance/transfer/restock），
    params_json 存操作参数，result_json 存执行结果。
    """
    id: str = Field(..., description="任务ID")
    type: ActionType = Field(..., description="操作类型")
    target_id: str = Field(..., description="操作目标ID（如 NearExpiryProduct.id）")
    store_id: str = Field(..., description="所属门店")
    assignee_id: str = Field(..., description="负责人")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="状态")
    params_json: dict = Field(default_factory=dict, description="操作参数字典")
    result_json: dict = Field(default_factory=dict, description="执行结果字典")
    priority: Priority = Field(default=Priority.MEDIUM, description="优先级")
    notes: Optional[str] = Field(None, description="备注")
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
