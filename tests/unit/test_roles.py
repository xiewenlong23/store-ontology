# ============================================================
# 角色权限测试 — 按实际 roles.py 实现重写
# ============================================================
import pytest
from app.auth.roles import (
    can_execute_discount,
    can_create_task,
    can_approve_task,
    get_role_level,
    get_store_manager_for_store,
    Role,
)


class TestCanExecuteDiscount:
    """测试折扣权限判断逻辑（按实际签名: 返回 tuple[bool, bool]）"""

    def test_clerk_below_70_percent(self):
        """店员发起折扣始终需要审批"""
        can_initiate, needs_approval = can_execute_discount("clerk", 0.50)
        assert can_initiate is True
        assert needs_approval is True

    def test_clerk_above_70_percent(self):
        """店员发起折扣始终需要审批（即使超过70%）"""
        can_initiate, needs_approval = can_execute_discount("clerk", 0.80)
        assert can_initiate is True
        assert needs_approval is True

    def test_store_manager_within_limit(self):
        """店长在权限内（≤70%）无需审批"""
        can_initiate, needs_approval = can_execute_discount("store_manager", 0.70)
        assert can_initiate is True
        assert needs_approval is False

    def test_store_manager_exceeds_limit(self):
        """店长超出权限（>70%）需总部审批"""
        can_initiate, needs_approval = can_execute_discount("store_manager", 0.80)
        assert can_initiate is True
        assert needs_approval is True

    def test_headquarters_within_limit(self):
        """总部在权限内（≤100%）无需审批"""
        can_initiate, needs_approval = can_execute_discount("headquarters", 0.90)
        assert can_initiate is True
        assert needs_approval is False

    def test_headquarters_exceeds_limit(self):
        """总部超出权限（>100%，即加价）需审批（实际折扣率不能超过1.0）"""
        can_initiate, needs_approval = can_execute_discount("headquarters", 1.50)
        assert can_initiate is True
        assert needs_approval is True

    def test_invalid_role(self):
        """无效角色：权限为0，0.5折扣率 > 权限上限，需要上报"""
        can_initiate, needs_approval = can_execute_discount("invalid_role", 0.50)
        assert can_initiate is True      # 角色合法但无折扣权限
        assert needs_approval is True     # 需上报审批


class TestCanCreateTask:
    """测试任务创建权限（按实际签名: 返回 tuple[bool, bool]）"""

    def test_clerk_can_create_task(self):
        """店员可以创建任务，需审批"""
        can_create, needs_approval = can_create_task("clerk")
        assert can_create is True
        assert needs_approval is True

    def test_store_manager_can_create_task(self):
        """店长可以创建任务，无需审批"""
        can_create, needs_approval = can_create_task("store_manager")
        assert can_create is True
        assert needs_approval is False

    def test_headquarters_can_create_task(self):
        """总部可以创建任务，无需审批"""
        can_create, needs_approval = can_create_task("headquarters")
        assert can_create is True
        assert needs_approval is False


class TestCanApproveTask:
    """测试任务审批权限"""

    def test_clerk_cannot_approve(self):
        assert can_approve_task("clerk") is False

    def test_store_manager_can_approve(self):
        assert can_approve_task("store_manager") is True

    def test_headquarters_can_approve(self):
        assert can_approve_task("headquarters") is True


class TestGetRoleLevel:
    """测试角色层级数值"""

    def test_role_levels(self):
        assert get_role_level("clerk") == 1
        assert get_role_level("store_manager") == 2
        assert get_role_level("headquarters") == 3

    def test_invalid_role_level(self):
        assert get_role_level("invalid_role") == 0


class TestGetStoreManagerForStore:
    """测试店长查询（Mock 数据）"""

    def test_store_manager(self):
        result = get_store_manager_for_store("STORE_001")
        assert result is not None
        assert result["user_id"] == "sm001"
        assert result["role"] == "store_manager"
        assert result["store_id"] == "STORE_001"

    def test_unknown_store(self):
        result = get_store_manager_for_store("UNKNOWN_STORE")
        assert result is None
