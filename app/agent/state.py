# ============================================================
# AgentState — Phase 2.2
# 继承 CopilotKitState，添加业务字段
# ============================================================
from typing import TypedDict, Optional, Literal
from datetime import datetime
from copilotkit import CopilotKitState


class DiscountTier(TypedDict):
    """折扣层级"""
    tier: Literal["T1", "T2", "T3"]
    rate: float
    rate_display: str
    remaining_days: int
    min_rate: float


class ExpiringProduct(TypedDict):
    """临期商品"""
    product_id: str
    product_name: str
    category: str
    shelf_date_days: int
    expiration_date: str
    remaining_days: int
    is_exempt: bool


class DiscountTask(TypedDict):
    """折扣任务"""
    task_id: str
    product_id: str
    product_name: str
    discount_tier: DiscountTier
    suggested_rate: float
    approved_rate: Optional[float]
    status: Literal["pending", "approved", "rejected", "executed", "cancelled"]
    created_by: str
    approver_id: Optional[str]
    created_at: str
    updated_at: str
    store_id: str


class AgentState(CopilotKitState):
    """
    门店大脑 Agent 全局状态

    继承 CopilotKitState，获得：
    - messages: list[BaseMessage]（对话历史）
    - properties: dict（CopilotKit 注入的用户属性）

    添加业务字段：
    """

    # ===== 用户上下文 =====
    user_id: str           # 飞书 open_id
    user_name: str
    employee_id: str
    store_id: str
    role: str              # clerk / store_manager / headquarters

    # ===== 会话 =====
    session_id: str

    # ===== 当前任务（折扣审批流） =====
    current_task: Optional[DiscountTask]
    pending_approvals: list[DiscountTask]
    recent_results: list[str]

    # ===== 工具返回数据（缓存） =====
    expiring_products_cache: list[ExpiringProduct]
    cache_timestamp: Optional[str]

    # ===== 中断控制（HITL） =====
    interrupt: bool
    interrupt_reason: Optional[str]
    interrupt_data: Optional[dict]

    # ===== LangSmith Trace =====
    trace_url: Optional[str]

    class Config:
        arbitrary_types_allowed = True
