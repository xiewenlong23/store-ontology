# ============================================================
# 折扣工具测试 — 按实际 discount_tools.py 实现重写
# ============================================================
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.agent.tools.discount_tools import (
    calculate_discount_tier,
    create_discount_task,
    approve_discount,
    reject_discount,
    TIER_RULES,
    EXEMPT_CATEGORIES,
)


class TestCalculateDiscountTier:
    """测试折扣层级计算"""

    async def test_tier_t1_normal_product(self):
        """T1: ≤7天 → 8折（20% off），最低保护价70%"""
        with patch("app.agent.tools.discount_tools.query_product_info", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {"product_id": "P001", "category": "dairy", "is_exempt": False}
            result = await calculate_discount_tier("P001", remaining_days=5, store_id="STORE_001")

        assert result["tier"] == "T1"
        assert result["rate"] == 0.20
        assert result["rate_display"] == "8折"
        assert result["min_rate"] == 0.70

    async def test_tier_t2_expiring_product(self):
        """T2: 8-14天 → 8.5折（15% off），最低保护价80%"""
        with patch("app.agent.tools.discount_tools.query_product_info", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {"product_id": "P001", "category": "dairy", "is_exempt": False}
            result = await calculate_discount_tier("P001", remaining_days=10, store_id="STORE_001")

        assert result["tier"] == "T2"
        assert result["rate"] == 0.15
        assert result["rate_display"] == "8.5折"
        assert result["min_rate"] == 0.80

    async def test_tier_t3_near_expiry(self):
        """T3: 15-30天 → 9折（10% off），最低保护价85%"""
        with patch("app.agent.tools.discount_tools.query_product_info", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {"product_id": "P001", "category": "dairy", "is_exempt": False}
            result = await calculate_discount_tier("P001", remaining_days=20, store_id="STORE_001")

        assert result["tier"] == "T3"
        assert result["rate"] == 0.10
        assert result["rate_display"] == "9折"
        assert result["min_rate"] == 0.85

    async def test_exempt_product(self):
        """豁免商品（烟草/酒类）不参与折扣"""
        with patch("app.agent.tools.discount_tools.query_product_info", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {"product_id": "P001", "category": "tobacco", "is_exempt": True}
            result = await calculate_discount_tier("P001", remaining_days=3, store_id="STORE_001")

        assert result["tier"] == "EXEMPT"
        assert result["rate"] == 0.0
        assert result["rate_display"] == "不参与折扣"


class TestCreateDiscountTask:
    """测试折扣任务创建"""

    async def test_create_pending_task(self):
        """创建待审批折扣任务"""
        tier = {"tier": "T1", "rate": 0.20, "rate_display": "8折", "remaining_days": 5, "min_rate": 0.70}
        task = await create_discount_task(
            product_id="P001",
            discount_tier="T1",
            suggested_rate=0.80,
            store_id="STORE_001",
            created_by="clerk001",
            product_name="牛奶",
        )

        assert task["status"] == "pending"
        assert task["product_id"] == "P001"
        assert task["store_id"] == "STORE_001"
        assert task["created_by"] == "clerk001"
        assert task["suggested_rate"] == 0.80
        assert task["approved_rate"] is None
        assert task["task_id"].startswith("DT")


class TestApproveRejectDiscount:
    """测试折扣审批和拒绝"""

    async def test_approve_discount(self):
        """店长批准折扣"""
        task = {
            "task_id": "DT12345678",
            "product_id": "P001",
            "status": "pending",
            "suggested_rate": 0.80,
            "approved_rate": None,
            "approver_id": "",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        result = await approve_discount(task, approved_rate=0.80, approver_id="sm001")

        assert result["status"] == "approved"
        assert result["approved_rate"] == 0.80
        assert result["approver_id"] == "sm001"

    async def test_reject_discount(self):
        """店长拒绝折扣"""
        task = {
            "task_id": "DT12345678",
            "product_id": "P001",
            "status": "pending",
            "approver_id": "",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        result = await reject_discount(task, reason="折扣率过高", approver_id="sm001")

        assert result["status"] == "rejected"
        assert result["approver_id"] == "sm001"
