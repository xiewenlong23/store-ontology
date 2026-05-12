"""
tests/unit/test_roles.py — Phase 7.1
角色权限矩阵单元测试
"""
import pytest
from app.auth.roles import (
    can_execute_discount,
    can_create_task,
    get_role_level,
    get_store_manager_for_store,
)


class TestCanExecuteDiscount:
    """折扣执行权限测试"""

    def test_clerk_below_70_percent(self):
        """店员 ≤70%：可申请，需审批"""
        can_initiate, needs_approval = can_execute_discount("clerk", 0.50)
        assert can_initiate is True
        assert needs_approval is True

    def test_clerk_above_70_percent(self):
        """店员 >70%：不可发起"""
        can_initiate, needs_approval = can_execute_discount("clerk", 0.80)
        assert can_initiate is False
        assert needs_approval is False

    def test_store_manager_below_70_percent(self):
        """店长 ≤70%：可直接执行"""
        can_initiate, needs_approval = can_execute_discount("store_manager", 0.50)
        assert can_initiate is True
        assert needs_approval is False

    def test_store_manager_above_70_percent(self):
        """店长 70-90%：可申请总部审批"""
        can_initiate, needs_approval = can_execute_discount("store_manager", 0.80)
        assert can_initiate is True
        assert needs_approval is True

    def test_headquarters_unlimited(self):
        """总部：无限制"""
        can_initiate, needs_approval = can_execute_discount("headquarters", 1.50)
        assert can_initiate is True
        assert needs_approval is False

    def test_invalid_role(self):
        """无效角色"""
        can_initiate, needs_approval = can_execute_discount("invalid_role", 0.50)
        assert can_initiate is False
        assert needs_approval is False


class TestCanCreateTask:
    """任务创建权限测试"""

    def test_clerk_can_create_task(self):
        """店员可创建任务"""
        assert can_create_task("clerk") is True

    def test_store_manager_can_create_task(self):
        """店长可创建任务"""
        assert can_create_task("store_manager") is True

    def test_headquarters_cannot_create_task(self):
        """总部不可创建任务"""
        assert can_create_task("headquarters") is False


class TestGetRoleLevel:
    """角色层级测试"""

    def test_role_levels(self):
        """角色层级：clerk=1 < store_manager=2 < headquarters=3"""
        assert get_role_level("clerk") == 1
        assert get_role_level("store_manager") == 2
        assert get_role_level("headquarters") == 3

    def test_invalid_role_level(self):
        """无效角色返回 0"""
        assert get_role_level("unknown") == 0


class TestGetStoreManagerForStore:
    """获取店长测试"""

    def test_store_manager(self):
        """已知门店有店长"""
        sm = get_store_manager_for_store("STORE_001")
        assert sm is not None
        assert sm["role"] == "store_manager"

    def test_unknown_store(self):
        """未知门店返回 None"""
        sm = get_store_manager_for_store("UNKNOWN_STORE")
        assert sm is None
