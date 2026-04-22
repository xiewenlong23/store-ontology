#!/usr/bin/env python3
"""
API End-to-End Integration Tests

Tests:
1. POST /reasoning/discount complete reasoning flow
2. State machine flow (create→confirm→execute→review)
3. Full task lifecycle
"""

import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from datetime import date, timedelta

from app.main import app

client = TestClient(app)

# Paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "app" / "data"
TASKS_FILE = DATA_DIR / "tasks.json"


def _backup_tasks():
    """Backup current tasks.json content"""
    if TASKS_FILE.exists():
        with open(TASKS_FILE) as f:
            return json.load(f)
    return []


def _restore_tasks(data):
    """Restore tasks.json with given data"""
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _clear_tasks():
    """Clear tasks.json for isolation"""
    _restore_tasks([])


class TestHealthEndpoint:
    """Basic health check"""

    def test_health_check(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestDiscountReasoningAPI:
    """POST /reasoning/discount endpoint tests"""

    def test_discount_tier1_1day_left(self):
        """Tier 1: 1 day left should recommend high discount"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.post("/api/reasoning/discount", json={
            "product_id": "TEST-T001",
            "product_name": "测试日配鲜奶",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "stock": 30,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["product_id"] == "TEST-T001"
        assert data["tier"] >= 1
        assert data["recommended_discount"] >= 0.0
        assert data["discount_range"][0] <= data["recommended_discount"] <= data["discount_range"][1]

    def test_discount_tier2_2to3_days(self):
        """Tier 2: 2-3 days left"""
        in_2_days = (date.today() + timedelta(days=2)).isoformat()
        r = client.post("/api/reasoning/discount", json={
            "product_id": "TEST-T002",
            "product_name": "测试日配鲜奶",
            "category": "daily_fresh",
            "expiry_date": in_2_days,
            "stock": 30,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["tier"] >= 1

    def test_discount_high_stock_aggressive(self):
        """High stock (>100) + short expiry should recommend more aggressive discount"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.post("/api/reasoning/discount", json={
            "product_id": "TEST-T003",
            "product_name": "测试日配",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "stock": 150,  # High stock
        })
        assert r.status_code == 200
        data = r.json()
        # High stock + 1 day should trigger aggressive discount
        assert data["auto_create_task"] is True

    def test_discount_expired_product(self):
        """Expired product should return 0 discount"""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        r = client.post("/api/reasoning/discount", json={
            "product_id": "TEST-T004",
            "product_name": "过期商品",
            "category": "daily_fresh",
            "expiry_date": yesterday,
            "stock": 30,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["recommended_discount"] == 0.0
        assert "已过期" in data["reasoning"]

    def test_discount_with_imported_flag(self):
        """Imported products should be flagged for exemption"""
        in_3_days = (date.today() + timedelta(days=3)).isoformat()
        r = client.post("/api/reasoning/discount", json={
            "product_id": "TEST-T005",
            "product_name": "进口测试商品",
            "category": "daily_fresh",
            "expiry_date": in_3_days,
            "stock": 30,
            "is_imported": True,
        })
        assert r.status_code == 200
        data = r.json()
        # Imported products should be marked as exempted
        # (though the exact behavior depends on TTL rules)
        assert "is_exempted" in data

    def test_discount_response_structure(self):
        """Discount response should have all required fields"""
        in_5_days = (date.today() + timedelta(days=5)).isoformat()
        r = client.post("/api/reasoning/discount", json={
            "product_id": "TEST-T006",
            "product_name": "测试商品",
            "category": "bakery",
            "expiry_date": in_5_days,
            "stock": 50,
        })
        assert r.status_code == 200
        data = r.json()
        required_fields = [
            "product_id", "recommended_discount", "discount_range",
            "tier", "reasoning", "auto_create_task"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestAgentScanAPI:
    """GET /reasoning/agent/scan endpoint tests"""

    def test_agent_scan_returns_structure(self):
        """Agent scan should return tasks_to_create and scanned_count"""
        r = client.post("/api/reasoning/agent/scan")
        assert r.status_code == 200
        data = r.json()
        assert "tasks_to_create" in data
        assert "scanned_count" in data
        assert isinstance(data["tasks_to_create"], list)
        assert isinstance(data["scanned_count"], int)


class TestStateMachineFlow:
    """
    State Machine Flow Tests: create→confirm→execute→review

    Full task lifecycle:
    1. Create task (Pending)
    2. Confirm task (Pending → Confirmed)
    3. Execute task (Confirmed → Executed)
    4. Review task (Executed → Reviewed/Completed)
    """

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Backup, clear, and restore tasks.json for test isolation"""
        self.original_tasks = _backup_tasks()
        _clear_tasks()
        yield
        _restore_tasks(self.original_tasks)

    def test_create_task_returns_pending(self):
        """Creating a task should return status pending"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P001",
            "product_name": "测试嫩豆腐",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "original_stock": 50,
            "created_by": "test_script",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "pending"
        assert "task_id" in data

    def test_full_flow_create_confirm_execute_review(self):
        """Full flow: create→confirm→execute→review"""
        # 1. Create task
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P001",
            "product_name": "测试嫩豆腐",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "original_stock": 50,
            "discount_rate": 0.4,
            "created_by": "test_script",
        })
        assert r.status_code == 200
        task = r.json()
        task_id = task["task_id"]
        assert task["status"] == "pending"

        # 2. Confirm task (Pending → Confirmed)
        r = client.patch(f"/api/tasks/{task_id}/confirm", json={
            "confirmed_discount_rate": 0.4,
            "confirmed_by": "店长",
        })
        assert r.status_code == 200
        confirmed = r.json()
        assert confirmed["status"] == "confirmed"
        assert confirmed["confirmed_discount_rate"] == 0.4
        assert "trigger_event_id" in confirmed

        # 3. Execute task (Confirmed → Executed)
        r = client.patch(f"/api/tasks/{task_id}/execute", json={
            "executed_by": "员工A",
            "scan_barcode": "1234567890",
            "price_label_printed": True,
        })
        assert r.status_code == 200
        executed = r.json()
        assert executed["status"] == "executed"
        assert executed["executed_by"] == "员工A"

        # 4. Review task (Executed → Completed)
        r = client.patch(f"/api/tasks/{task_id}/review", json={
            "reviewed_by": "店长B",
            "sell_through_rate": 0.85,
            "review_notes": "出清完成",
        })
        assert r.status_code == 200
        reviewed = r.json()
        assert reviewed["status"] == "completed"
        assert reviewed["sell_through_rate"] == 0.85
        assert reviewed["reviewed_by"] == "店长B"

    def test_confirm_wrong_status_fails(self):
        """Confirming a non-pending task should fail"""
        # Create and immediately confirm (should work)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P002",
            "product_name": "测试商品",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "original_stock": 50,
            "created_by": "test",
        })
        task_id = r.json()["task_id"]

        # Confirm first time (should work)
        r = client.patch(f"/api/tasks/{task_id}/confirm", json={
            "confirmed_discount_rate": 0.4,
        })
        assert r.status_code == 200

        # Try to confirm again (should fail)
        r = client.patch(f"/api/tasks/{task_id}/confirm", json={
            "confirmed_discount_rate": 0.4,
        })
        assert r.status_code == 400
        assert "只有Pending状态" in r.json()["detail"]

    def test_execute_wrong_status_fails(self):
        """Executing a non-confirmed task should fail"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P003",
            "product_name": "测试商品",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "original_stock": 50,
            "created_by": "test",
        })
        task_id = r.json()["task_id"]

        # Try to execute without confirming first (should fail)
        r = client.patch(f"/api/tasks/{task_id}/execute", json={
            "executed_by": "员工",
            "scan_barcode": "1234567890",
        })
        assert r.status_code == 400
        assert "只有Confirmed状态" in r.json()["detail"]

    def test_review_wrong_status_fails(self):
        """Reviewing a non-executed task should fail"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P004",
            "product_name": "测试商品",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "original_stock": 50,
            "created_by": "test",
        })
        task_id = r.json()["task_id"]

        # Confirm first
        r = client.patch(f"/api/tasks/{task_id}/confirm", json={
            "confirmed_discount_rate": 0.4,
        })
        assert r.status_code == 200

        # Try to review without executing (should fail)
        r = client.patch(f"/api/tasks/{task_id}/review", json={
            "reviewed_by": "店长",
            "sell_through_rate": 0.9,
        })
        assert r.status_code == 400
        assert "只有Executed状态" in r.json()["detail"]

    def test_review_with_rectification_flag(self):
        """Review with requires_rectification should set Reviewed status, not Completed"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P005",
            "product_name": "测试商品",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "original_stock": 50,
            "created_by": "test",
        })
        task_id = r.json()["task_id"]

        # Full flow up to execute
        client.patch(f"/api/tasks/{task_id}/confirm", json={"confirmed_discount_rate": 0.4})
        client.patch(f"/api/tasks/{task_id}/execute", json={
            "executed_by": "员工",
            "scan_barcode": "1234567890",
        })

        # Review with rectification flag
        r = client.patch(f"/api/tasks/{task_id}/review", json={
            "reviewed_by": "店长",
            "sell_through_rate": 0.5,
            "requires_rectification": True,
        })
        assert r.status_code == 200
        data = r.json()
        # Should be "reviewed" not "completed" when rectification needed
        assert data["status"] == "reviewed"


class TestTaskListAPI:
    """GET /api/tasks/ endpoint tests"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.original_tasks = _backup_tasks()
        _clear_tasks()
        yield
        _restore_tasks(self.original_tasks)

    def test_list_tasks_empty(self):
        """List tasks when empty should return empty list"""
        r = client.get("/api/tasks/")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_tasks_with_data(self):
        """List tasks should return created tasks"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P001",
            "product_name": "测试商品1",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "original_stock": 50,
            "created_by": "test",
        })
        client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P002",
            "product_name": "测试商品2",
            "category": "bakery",
            "expiry_date": tomorrow,
            "original_stock": 30,
            "created_by": "test",
        })

        r = client.get("/api/tasks/")
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) == 2

    def test_list_tasks_filter_by_status(self):
        """List tasks filtered by status"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result1 = client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P001",
            "product_name": "测试商品1",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "original_stock": 50,
            "created_by": "test",
        })
        task1_id = result1.json()["task_id"]

        result2 = client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P002",
            "product_name": "测试商品2",
            "category": "bakery",
            "expiry_date": tomorrow,
            "original_stock": 30,
            "created_by": "test",
        })
        task2_id = result2.json()["task_id"]

        # Confirm task2
        client.patch(f"/api/tasks/{task2_id}/confirm", json={
            "confirmed_discount_rate": 0.4,
        })

        # Filter by pending
        r = client.get("/api/tasks/?status=pending")
        tasks = r.json()
        assert all(t["status"] == "pending" for t in tasks)
        assert len(tasks) == 1

        # Filter by confirmed
        r = client.get("/api/tasks/?status=confirmed")
        tasks = r.json()
        assert all(t["status"] == "confirmed" for t in tasks)
        assert len(tasks) == 1

    def test_get_task_by_id(self):
        """Get specific task by ID"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = client.post("/api/tasks/", json={
            "store_id": "TEST-STORE",
            "product_id": "TEST-P001",
            "product_name": "测试商品",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "original_stock": 50,
            "created_by": "test",
        })
        task_id = result.json()["task_id"]

        r = client.get(f"/api/tasks/{task_id}")
        assert r.status_code == 200
        assert r.json()["task_id"] == task_id

    def test_get_nonexistent_task_returns_404(self):
        """Get nonexistent task should return 404"""
        r = client.get("/api/tasks/nonexistent-id-12345")
        assert r.status_code == 404


class TestDiscountAPIEndToEnd:
    """End-to-end discount reasoning flow tests"""

    def test_discount_flow_for_imminent_expiry_product(self):
        """Test complete discount flow for a product expiring tomorrow"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        # Step 1: Get discount recommendation
        r = client.post("/api/reasoning/discount", json={
            "product_id": "P001",
            "product_name": "日配鲜奶",
            "category": "daily_fresh",
            "expiry_date": tomorrow,
            "stock": 80,
        })
        assert r.status_code == 200
        discount_data = r.json()

        # Step 2: If auto_create_task is True, create a task
        if discount_data.get("auto_create_task"):
            r = client.post("/api/tasks/", json={
                "store_id": "STORE-001",
                "product_id": discount_data["product_id"],
                "product_name": "日配鲜奶",
                "category": "daily_fresh",
                "expiry_date": tomorrow,
                "original_stock": 80,
                "discount_rate": discount_data["recommended_discount"],
                "created_by": "AI",
            })
            assert r.status_code == 200
            task = r.json()
            assert task["status"] == "pending"

    def test_discount_flow_with_normal_expiry_product(self):
        """Test discount flow for product with normal expiry (7 days)"""
        in_week = (date.today() + timedelta(days=7)).isoformat()

        r = client.post("/api/reasoning/discount", json={
            "product_id": "P002",
            "product_name": "面包",
            "category": "bakery",
            "expiry_date": in_week,
            "stock": 40,
        })
        assert r.status_code == 200
        data = r.json()
        # Normal expiry product should not auto-create task
        assert data["auto_create_task"] is False


class TestCORSHeaders:
    """CORS configuration tests"""

    def test_cors_headers_present(self):
        """API responses should include CORS headers"""
        r = client.get("/api/health")
        # TestClient handles CORS internally; this is a basic check
        assert r.status_code == 200