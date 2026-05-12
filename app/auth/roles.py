# ============================================================
# 角色权限矩阵 — Phase 4.2
# 店员 / 店长 / 总部 三级权限定义
# 配置来源：config/roles.yaml（业务规则外置）
# ============================================================
from typing import Literal
from app.agent.tools import get_tools_for_role

Role = Literal["clerk", "store_manager", "headquarters"]


# ========== 折扣权限 ==========
DISCOUNT_RATE_LIMITS = {
    "clerk": 0,          # 店员：不能发起折扣（只能推荐）
    "store_manager": 0.70,  # 店长：≤70% 直接通过，>70% 需总部审批
    "headquarters": 1.0,   # 总部：无限制
}

# ========== 任务权限 ==========
TASK_CREATE_ALLOWED = {
    "clerk": True,        # 店员可创建（需审批）
    "store_manager": True,  # 店长可创建（直接通过）
    "headquarters": True,   # 总部可创建
}

TASK_APPROVE_ALLOWED = {
    "clerk": False,       # 店员不能审批
    "store_manager": True,  # 店长可审批本店任务
    "headquarters": True,   # 总部可审批所有任务
}

# ========== 查询权限（数据脱敏）============
COST_PRICE_VISIBLE = {
    "clerk": False,      # 店员：看不到进价
    "store_manager": True,
    "headquarters": True,
}

SUPPLIER_INFO_VISIBLE = {
    "clerk": False,
    "store_manager": False,  # 店长也隐藏供应商信息
    "headquarters": True,
}


def can_execute_discount(role: Role, rate: float) -> tuple[bool, bool]:
    """
    判断某角色是否能执行/申请某折扣率。

    注意："发起折扣"和"执行折扣"是不同的操作：
    - 店员可以"发起折扣申请"（提交申请单，触发审批流）
    - 店长/总部可以直接"执行"折扣（在权限内）或"审批"折扣（超出权限）

    返回 (can_initiate, needs_approval)
    - can_initiate: 是否可以发起（店员=申请，店长/总部=执行）
    - needs_approval: 是否需要审批（店员始终需要，店长看折扣率）
    """
    max_rate = DISCOUNT_RATE_LIMITS.get(role, 0)

    # 店员：可以发起折扣申请，但始终需要审批
    if role == "clerk":
        return True, True  # 店员可以申请折扣，需要店长审批

    # 店长/总部：看折扣率是否在权限内
    if rate <= max_rate:
        return True, False  # 权限内，无需审批（直接执行）
    return True, True  # 超出权限，需上报审批


def can_approve_task(role: Role) -> bool:
    """判断某角色是否能审批任务"""
    return TASK_APPROVE_ALLOWED.get(role, False)


def can_create_task(role: Role) -> tuple[bool, bool]:
    """
    判断某角色是否能创建任务。
    返回 (can_create, needs_approval)
    """
    if not TASK_CREATE_ALLOWED.get(role, False):
        return False, False
    if role == "clerk":
        return True, True  # 店员创建需审批
    return True, False  # 店长/总部直接通过


def get_allowed_tools(role: Role) -> list[str]:
    """返回某角色可使用的工具列表（来自 skills.yaml 动态配置）"""
    return get_tools_for_role(role)


async def resolve_user_role(user_id: str, store_id: str = None) -> Role:
    """
    从 GraphDB 查询用户实际角色。
    兜底默认返回 clerk（最低权限）。
    """
    from app.agent.tools.sparql_tools import query_employee_role

    try:
        role_str = await query_employee_role(user_id, store_id)
        if role_str in ("store_manager", "headquarters", "clerk"):
            return role_str
    except Exception:
        pass

    # 默认最低权限
    return "clerk"
