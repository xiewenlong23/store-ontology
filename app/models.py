from enum import Enum
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

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

class ReductionTask(BaseModel):
    task_id: str
    store_id: str
    product_id: str
    product_name: str
    category: ProductCategory
    expiry_date: date
    original_stock: int
    discount_rate: Optional[float] = None
    sell_through_rate: Optional[float] = None
    status: TaskStatus = TaskStatus.PENDING
    created_by: str
    created_at: Optional[datetime] = None

class Product(BaseModel):
    product_id: str
    name: str
    category: ProductCategory
    expiry_date: date
    stock: int
    in_reduction: bool = False
