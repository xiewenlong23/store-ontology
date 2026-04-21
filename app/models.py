from enum import Enum
from pydantic import BaseModel, Field
import uuid
from datetime import date, datetime
from typing import Optional

class TaskStatus(str, Enum):
    """完整状态机：Pending→Confirmed→Executed→Reviewed→Completed"""
    PENDING = "pending"       # 待确认（系统推理推荐，待店长审批）
    CONFIRMED = "confirmed"   # 已确认（店长或AI自动确认）
    EXECUTED = "executed"     # 已执行（员工完成IF枪扫描+价签打印）
    REVIEWED = "reviewed"     # 已复核（店长复核售罄率，任务闭环）
    COMPLETED = "completed"   # 已完成（归档/取消/超时）

class ProductCategory(str, Enum):
    DAILY_FRESH = "daily_fresh"      # 日配
    BAKERY = "bakery"                # 烘焙
    FRESH = "fresh"                  # 生鲜
    MEAT_POULTRY = "meat_poultry"    # 肉禽
    SEAFOOD = "seafood"              # 水产
    DAIRY = "dairy"                  # 乳品
    FROZEN = "frozen"                # 冷冻食品
    BEVERAGE = "beverage"            # 饮品
    SNACK = "snack"                  # 休闲食品
    GRAIN_OIL = "grain_oil"          # 米面粮油

class ActionType(str, Enum):
    """店长自然语言意图分类"""
    QUERY_PENDING = "query_pending"           # 查询临期待出清商品
    QUERY_TASKS = "query_tasks"               # 查询任务状态/列表
    QUERY_DISCOUNT = "query_discount"           # 查询折扣建议
    CREATE_TASK = "create_task"               # 创建出清任务
    CONFIRM_TASK = "confirm_task"             # 确认任务（审批）
    EXECUTE_TASK = "execute_task"             # 执行任务（扫描+打印）
    REVIEW_TASK = "review_task"               # 复核任务（售罄率闭环）
    REPORT_COMPLETION = "report_completion"   # 报告任务完成
    SCAN_INVENTORY = "scan_inventory"         # 扫描库存
    UNKNOWN = "unknown"                       # 无法分类

class RiskLevel(str, Enum):
    """风险等级，用于AI自动确认阈值"""
    LOW = "low"      # 低风险：AI自动确认
    MEDIUM = "medium"  # 中风险：需店长确认
    HIGH = "high"    # 高风险：需店长确认

class ExemptionType(str, Enum):
    """豁免类型枚举"""
    IMPORTED = "imported"              # 进口商品
    ORGANIC = "organic"                # 有机绿色食品
    ALREADY_PROMOTED = "already_promoted"  # 已参与促销
    NEW_ARRIVAL = "new_arrival"        # 新上架商品
    HQ_BAN = "hq_ban"                  # 总部禁止打折
    STORE_LOCAL = "store_local"        # 门店本地豁免

class ReductionTask(BaseModel):
    task_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    store_id: str
    product_id: str
    product_name: str
    category: ProductCategory
    expiry_date: date
    original_stock: int
    discount_rate: Optional[float] = None
    confirmed_discount_rate: Optional[float] = None
    executed_discount_rate: Optional[float] = None
    sell_through_rate: Optional[float] = None
    status: TaskStatus = TaskStatus.PENDING
    created_by: str
    created_at: Optional[datetime] = None
    # 豁免信息
    exemption_type: Optional[ExemptionType] = None
    exemption_reason: Optional[str] = None
    # 确认信息
    confirmed_notes: Optional[str] = None
    auto_confirmed: bool = False
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    # 执行信息
    executed_by: Optional[str] = None
    executed_at: Optional[datetime] = None
    scan_barcode: Optional[str] = None
    price_label_printed: bool = False
    # 复核信息
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    # 风险等级
    risk_level: Optional[RiskLevel] = None
    # 触发事件
    trigger_event_id: Optional[str] = None

class Product(BaseModel):
    product_id: str
    name: str
    category: ProductCategory
    expiry_date: date
    stock: int
    in_reduction: bool = False
