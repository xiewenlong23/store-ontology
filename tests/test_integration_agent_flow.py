#!/usr/bin/env python3
"""
Agent Multi-Tool Collaboration Integration Tests

Tests the coordination between multiple tools:
1. query_pending_products + create_task + confirm_task flow
2. Full workflow from scanning products to task confirmation
3. Tool registry and dispatch integration
"""

import pytest
import json
from pathlib import Path
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

# Paths
# NOTE: store_tools.py uses Path(__file__).parent.parent.parent / "data" (repo_root/data)
# So we must use the same path for test isolation to work correctly
REPO_ROOT = Path(__file__).parent.parent
PRODUCTS_FILE = REPO_ROOT / "data" / "products.json"
TASKS_FILE = REPO_ROOT / "data" / "tasks.json"


def _backup_data():
    """Backup products and tasks data"""
    products_backup = json.loads(PRODUCTS_FILE.read_text()) if PRODUCTS_FILE.exists() else []
    tasks_backup = json.loads(TASKS_FILE.read_text()) if TASKS_FILE.exists() else []
    return products_backup, tasks_backup


def _restore_data(products, tasks):
    """Restore products and tasks data"""
    PRODUCTS_FILE.write_text(json.dumps(products, indent=2, ensure_ascii=False))
    TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False))


def _setup_test_products():
    """Setup test products with varying expiry dates"""
    today = date.today()
    test_products = [
        {
            "product_id": "AGENT-TEST-P001",
            "name": "测试日配鲜奶",
            "category": "daily_fresh",
            "store_id": "STORE-001",
            "production_date": (today - timedelta(days=5)).isoformat(),
            "expiry_date": (today + timedelta(days=1)).isoformat(),  # Expiring tomorrow!
            "stock": 60,
            "price": 25.0,
            "original_price": 35.0,
            "is_imported": False,
            "is_organic": False,
            "is_promoted": False,
            "arrival_days": 5,
            "in_reduction": False,
        },
        {
            "product_id": "AGENT-TEST-P002",
            "name": "测试烘焙面包",
            "category": "bakery",
            "store_id": "STORE-001",
            "production_date": (today - timedelta(days=2)).isoformat(),
            "expiry_date": (today + timedelta(days=2)).isoformat(),  # Expiring in 2 days
            "stock": 40,
            "price": 15.0,
            "original_price": 20.0,
            "is_imported": False,
            "is_organic": False,
            "is_promoted": False,
            "arrival_days": 2,
            "in_reduction": False,
        },
        {
            "product_id": "AGENT-TEST-P003",
            "name": "正常保质期商品",
            "category": "snack",
            "store_id": "STORE-001",
            "production_date": (today - timedelta(days=10)).isoformat(),
            "expiry_date": (today + timedelta(days=30)).isoformat(),  # Still 30 days left
            "stock": 100,
            "price": 10.0,
            "original_price": 15.0,
            "is_imported": False,
            "is_organic": False,
            "is_promoted": False,
            "arrival_days": 10,
            "in_reduction": False,
        },
    ]
    PRODUCTS_FILE.write_text(json.dumps(test_products, indent=2, ensure_ascii=False))
    return test_products


def _clear_tasks():
    """Clear tasks for isolation"""
    TASKS_FILE.write_text("[]")


class TestToolRegistryIntegration:
    """Tool registry and basic tool function tests"""

    def test_all_tools_registered(self):
        """All expected tools should be registered"""
        # Trigger tool registration
        import app.tools.store_tools
        from app.tools.registry import registry

        tools = registry.get_all_tools()
        expected_tools = [
            "query_pending_products",
            "query_pending_with_discount",
            "query_tasks",
            "query_discount_rules",
            "create_task",
            "confirm_task",
            "execute_task",
            "review_task",
            "query_discount",
        ]
        for name in expected_tools:
            assert name in tools, f"Tool {name} not registered. Registered: {list(tools.keys())}"

    def test_tool_schemas_valid(self):
        """All tool schemas should have required fields"""
        import app.tools.store_tools
        from app.tools.registry import registry

        tools = registry.get_all_tools()
        for name, entry in tools.items():
            assert "name" in entry.schema, f"{name}: missing 'name'"
            assert "description" in entry.schema, f"{name}: missing 'description'"
            assert "parameters" in entry.schema, f"{name}: missing 'parameters'"


class TestQueryPendingProductsTool:
    """query_pending_products tool integration tests"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.products_backup, self.tasks_backup = _backup_data()
        _setup_test_products()
        _clear_tasks()
        yield
        _restore_data(self.products_backup, self.tasks_backup)

    def test_query_pending_products_returns_imminent_expiry(self):
        """query_pending_products should return products expiring soon"""
        import app.tools.store_tools
        from app.tools.registry import registry

        result = registry.dispatch(
            "query_pending_products",
            args={"category": "daily_fresh", "days_threshold": 7},
        )

        assert result["success"] is True
        assert "products" in result
        assert result["count"] >= 1

        # Should find the daily_fresh product expiring tomorrow
        p001 = next((p for p in result["products"] if p["product_id"] == "AGENT-TEST-P001"), None)
        assert p001 is not None
        assert p001["days_left"] == 1

    def test_query_pending_products_filter_by_category(self):
        """query_pending_products should filter by category"""
        import app.tools.store_tools
        from app.tools.registry import registry

        result = registry.dispatch(
            "query_pending_products",
            args={"category": "bakery", "days_threshold": 7},
        )

        assert result["success"] is True
        assert all(p["category"] == "bakery" for p in result["products"])

    def test_query_pending_products_days_threshold(self):
        """query_pending_products should respect days_threshold"""
        import app.tools.store_tools
        from app.tools.registry import registry

        # With threshold=7, should find products expiring in 1-2 days
        result = registry.dispatch(
            "query_pending_products",
            args={"days_threshold": 7},
        )
        assert result["count"] >= 2  # P001 (1 day) and P002 (2 days)

        # With threshold=2, should find products with days_left < 2 (i.e., only P001 with 1 day)
        result_strict = registry.dispatch(
            "query_pending_products",
            args={"days_threshold": 2},
        )
        assert result_strict["count"] == 1  # Only P001 (1 day)


class TestCreateTaskTool:
    """create_task tool integration tests"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.products_backup, self.tasks_backup = _backup_data()
        _setup_test_products()
        _clear_tasks()
        yield
        _restore_data(self.products_backup, self.tasks_backup)

    def test_create_task_basic(self):
        """create_task should create a task successfully"""
        import app.tools.store_tools
        from app.tools.registry import registry

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = registry.dispatch(
            "create_task",
            args={
                "product_id": "AGENT-TEST-P001",
                "product_name": "测试日配鲜奶",
                "category": "daily_fresh",
                "discount_rate": 0.4,
                "original_stock": 60,
                "expiry_date": tomorrow,
                "store_id": "STORE-001",
                "created_by": "店长",
                "urgency": "high",
            },
        )

        assert result["success"] is True
        assert "task_id" in result
        assert "嫩豆腐" in result["message"] or "测试日配" in result["message"]

    def test_create_task_persisted(self):
        """Created task should be persisted in tasks.json"""
        import app.tools.store_tools
        from app.tools.registry import registry

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = registry.dispatch(
            "create_task",
            args={
                "product_id": "AGENT-TEST-P001",
                "product_name": "测试日配鲜奶",
                "category": "daily_fresh",
                "discount_rate": 0.4,
                "original_stock": 60,
                "expiry_date": tomorrow,
            },
        )

        tasks = json.loads(TASKS_FILE.read_text())
        assert len(tasks) == 1
        assert tasks[0]["product_id"] == "AGENT-TEST-P001"
        assert tasks[0]["status"] == "pending"


class TestConfirmTaskTool:
    """confirm_task tool integration tests"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.products_backup, self.tasks_backup = _backup_data()
        _setup_test_products()
        _clear_tasks()
        yield
        _restore_data(self.products_backup, self.tasks_backup)

    def _create_task(self, product_id="AGENT-TEST-P001", discount_rate=0.4):
        """Helper to create a task and return task_id"""
        import app.tools.store_tools
        from app.tools.registry import registry

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = registry.dispatch(
            "create_task",
            args={
                "product_id": product_id,
                "product_name": "测试商品",
                "category": "daily_fresh",
                "discount_rate": discount_rate,
                "original_stock": 60,
                "expiry_date": tomorrow,
            },
        )
        return result["task_id"]

    def test_confirm_task_basic(self):
        """confirm_task should confirm a pending task"""
        import app.tools.store_tools
        from app.tools.registry import registry

        task_id = self._create_task()
        result = registry.dispatch(
            "confirm_task",
            args={
                "task_id": task_id,
                "confirmed_discount_rate": 0.4,
                "confirmed_by": "店长",
            },
        )

        assert result["success"] is True
        assert "已确认" in result["message"]

    def test_confirm_task_updates_status(self):
        """Confirmed task should have status=confirmed in persistence"""
        import app.tools.store_tools
        from app.tools.registry import registry

        task_id = self._create_task()
        registry.dispatch(
            "confirm_task",
            args={"task_id": task_id, "confirmed_discount_rate": 0.4},
        )

        tasks = json.loads(TASKS_FILE.read_text())
        confirmed_task = next(t for t in tasks if t["task_id"] == task_id)
        assert confirmed_task["status"] == "confirmed"

    def test_confirm_nonexistent_task_fails(self):
        """Confirming nonexistent task should fail gracefully"""
        import app.tools.store_tools
        from app.tools.registry import registry

        result = registry.dispatch(
            "confirm_task",
            args={"task_id": "nonexistent-task-id", "confirmed_discount_rate": 0.4},
        )

        assert result["success"] is False
        assert "不存在" in result["error"]

    def test_confirm_already_confirmed_task_fails(self):
        """Confirming an already confirmed task should fail"""
        import app.tools.store_tools
        from app.tools.registry import registry

        task_id = self._create_task()
        # First confirmation
        registry.dispatch("confirm_task", args={"task_id": task_id, "confirmed_discount_rate": 0.4})
        # Second confirmation attempt
        result = registry.dispatch("confirm_task", args={"task_id": task_id, "confirmed_discount_rate": 0.4})

        assert result["success"] is False
        assert "只有Pending状态" in result["error"]


class TestMultiToolWorkflow:
    """Multi-tool workflow coordination tests"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.products_backup, self.tasks_backup = _backup_data()
        _setup_test_products()
        _clear_tasks()
        yield
        _restore_data(self.products_backup, self.tasks_backup)

    def test_full_workflow_query_create_confirm(self):
        """Complete workflow: query_pending → create_task → confirm_task"""
        import app.tools.store_tools
        from app.tools.registry import registry

        # Step 1: Query pending products
        pending_result = registry.dispatch(
            "query_pending_products",
            args={"days_threshold": 7},
        )
        assert pending_result["success"] is True
        assert pending_result["count"] >= 2

        # Step 2: Create task for the first pending product
        p001 = pending_result["products"][0]
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        create_result = registry.dispatch(
            "create_task",
            args={
                "product_id": p001["product_id"],
                "product_name": p001["name"],
                "category": p001["category"],
                "discount_rate": 0.4,
                "original_stock": p001["stock"],
                "expiry_date": tomorrow,
            },
        )
        assert create_result["success"] is True
        task_id = create_result["task_id"]

        # Step 3: Confirm the task
        confirm_result = registry.dispatch(
            "confirm_task",
            args={
                "task_id": task_id,
                "confirmed_discount_rate": 0.4,
                "confirmed_by": "店长",
            },
        )
        assert confirm_result["success"] is True

        # Verify final state
        tasks = json.loads(TASKS_FILE.read_text())
        confirmed = next(t for t in tasks if t["task_id"] == task_id)
        assert confirmed["status"] == "confirmed"

    def test_workflow_query_multiple_products_create_multiple_tasks(self):
        """Query pending products and create tasks for multiple"""
        import app.tools.store_tools
        from app.tools.registry import registry

        # Query all pending products
        pending_result = registry.dispatch(
            "query_pending_products",
            args={"days_threshold": 7},
        )
        assert pending_result["count"] >= 2

        # Create tasks for products with days_left <= 2 (critical)
        critical_products = [p for p in pending_result["products"] if p["days_left"] <= 2]
        assert len(critical_products) >= 1

        task_ids = []
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        for product in critical_products:
            result = registry.dispatch(
                "create_task",
                args={
                    "product_id": product["product_id"],
                    "product_name": product["name"],
                    "category": product["category"],
                    "discount_rate": 0.4,
                    "original_stock": product["stock"],
                    "expiry_date": product["expiry_date"],
                },
            )
            if result["success"]:
                task_ids.append(result["task_id"])

        # Verify tasks created
        tasks = json.loads(TASKS_FILE.read_text())
        assert len(tasks) == len(task_ids)
        assert all(t["status"] == "pending" for t in tasks)


class TestExecuteAndReviewTools:
    """execute_task and review_task tool integration"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.products_backup, self.tasks_backup = _backup_data()
        _setup_test_products()
        _clear_tasks()
        yield
        _restore_data(self.products_backup, self.tasks_backup)

    def _create_and_confirm_task(self):
        """Helper to create and confirm a task, returning task_id"""
        import app.tools.store_tools
        from app.tools.registry import registry

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = registry.dispatch(
            "create_task",
            args={
                "product_id": "AGENT-TEST-P001",
                "product_name": "测试商品",
                "category": "daily_fresh",
                "discount_rate": 0.4,
                "original_stock": 60,
                "expiry_date": tomorrow,
            },
        )
        task_id = result["task_id"]

        registry.dispatch(
            "confirm_task",
            args={"task_id": task_id, "confirmed_discount_rate": 0.4},
        )
        return task_id

    def test_execute_task_basic(self):
        """execute_task should mark task as executed"""
        import app.tools.store_tools
        from app.tools.registry import registry

        task_id = self._create_and_confirm_task()

        result = registry.dispatch(
            "execute_task",
            args={
                "task_id": task_id,
                "executed_by": "员工A",
                "scan_barcode": "1234567890",
                "price_label_printed": True,
            },
        )

        assert result["success"] is True
        assert "已执行" in result["message"]

    def test_execute_task_updates_status(self):
        """Executed task should have status=executed"""
        import app.tools.store_tools
        from app.tools.registry import registry

        task_id = self._create_and_confirm_task()
        registry.dispatch(
            "execute_task",
            args={"task_id": task_id, "executed_by": "员工A"},
        )

        tasks = json.loads(TASKS_FILE.read_text())
        executed = next(t for t in tasks if t["task_id"] == task_id)
        assert executed["status"] == "executed"

    def test_review_task_basic(self):
        """review_task should complete the task lifecycle"""
        import app.tools.store_tools
        from app.tools.registry import registry

        task_id = self._create_and_confirm_task()
        registry.dispatch("execute_task", args={"task_id": task_id, "executed_by": "员工A"})

        result = registry.dispatch(
            "review_task",
            args={
                "task_id": task_id,
                "reviewed_by": "店长",
                "sell_through_rate": 0.85,
            },
        )

        assert result["success"] is True
        assert result["final_status"] == "已完成"

    def test_review_task_with_rectification(self):
        """review_task with requires_rectification should set reviewed status"""
        import app.tools.store_tools
        from app.tools.registry import registry

        task_id = self._create_and_confirm_task()
        registry.dispatch("execute_task", args={"task_id": task_id, "executed_by": "员工A"})

        result = registry.dispatch(
            "review_task",
            args={
                "task_id": task_id,
                "reviewed_by": "店长",
                "sell_through_rate": 0.4,
                "requires_rectification": True,
            },
        )

        assert result["success"] is True
        assert result["final_status"] == "需要整改"

        tasks = json.loads(TASKS_FILE.read_text())
        reviewed = next(t for t in tasks if t["task_id"] == task_id)
        assert reviewed["status"] == "reviewed"


class TestQueryDiscountTool:
    """query_discount tool integration tests"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.products_backup, self.tasks_backup = _backup_data()
        _setup_test_products()
        _clear_tasks()
        yield
        _restore_data(self.products_backup, self.tasks_backup)

    def test_query_discount_suggestion(self):
        """query_discount without discount_rate should return suggestion"""
        import app.tools.store_tools
        from app.tools.registry import registry

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = registry.dispatch(
            "query_discount",
            args={
                "product_id": "AGENT-TEST-P001",
                "product_name": "测试日配鲜奶",
                "category": "daily_fresh",
                "expiry_date": tomorrow,
                "stock": 60,
            },
        )

        assert result["success"] is True
        assert "recommended_discount" in result

    def test_query_discount_explanation(self):
        """query_discount with discount_rate should return explanation"""
        import app.tools.store_tools
        from app.tools.registry import registry

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = registry.dispatch(
            "query_discount",
            args={
                "product_id": "AGENT-TEST-P001",
                "product_name": "测试日配鲜奶",
                "category": "daily_fresh",
                "expiry_date": tomorrow,
                "stock": 60,
                "discount_rate": 0.4,
            },
        )

        assert result["success"] is True
        assert "explanation" in result


class TestQueryTasksTool:
    """query_tasks tool integration tests"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.products_backup, self.tasks_backup = _backup_data()
        _setup_test_products()
        _clear_tasks()
        yield
        _restore_data(self.products_backup, self.tasks_backup)

    def _create_task(self, status="pending"):
        """Helper to create a task"""
        import app.tools.store_tools
        from app.tools.registry import registry

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = registry.dispatch(
            "create_task",
            args={
                "product_id": f"AGENT-TEST-{status}",
                "product_name": f"测试{status}",
                "category": "daily_fresh",
                "discount_rate": 0.4,
                "original_stock": 60,
                "expiry_date": tomorrow,
            },
        )
        task_id = result["task_id"]

        if status == "confirmed":
            registry.dispatch("confirm_task", args={"task_id": task_id, "confirmed_discount_rate": 0.4})

        return task_id

    def test_query_tasks_all(self):
        """query_tasks without filter should return all tasks"""
        import app.tools.store_tools
        from app.tools.registry import registry

        self._create_task("pending")
        self._create_task("confirmed")

        result = registry.dispatch("query_tasks", args={})

        assert result["success"] is True
        assert result["count"] == 2

    def test_query_tasks_filter_by_status(self):
        """query_tasks with status filter should return filtered tasks"""
        import app.tools.store_tools
        from app.tools.registry import registry

        self._create_task("pending")
        self._create_task("confirmed")

        result = registry.dispatch("query_tasks", args={"status": "confirmed"})

        assert result["success"] is True
        assert result["count"] == 1
        assert result["tasks"][0]["status"] == "confirmed"


class TestAgentExecutorIntegration:
    """Agent Executor multi-step workflow tests (mocked LLM)"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.products_backup, self.tasks_backup = _backup_data()
        _setup_test_products()
        _clear_tasks()
        yield
        _restore_data(self.products_backup, self.tasks_backup)

    @patch("app.services.agent_executor.get_minimax_llm")
    def test_executor_query_pending_products_flow(self, mock_get_llm):
        """Test AgentExecutor routing to query_pending_products"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_llm.chat.side_effect = [
            '{"tool": "query_pending_products", "args": {"days_threshold": 7}, "reasoning": "查询临期商品", "continue": true}',
            '{"reasoning": "当前有2个临期商品需要关注。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("有哪些临期商品")

        assert result["success"] is True
        assert result["tool_name"] == "query_pending_products"
        assert result["steps"] == 2

    @patch("app.services.agent_executor.get_minimax_llm")
    @patch("app.tools.registry.registry.dispatch")
    def test_executor_create_task_flow(self, mock_dispatch, mock_get_llm):
        """Test AgentExecutor routing to create_task"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_dispatch.return_value = {
            "success": True,
            "task_id": "test-task-123",
            "message": "任务创建成功",
        }

        mock_llm.chat.side_effect = [
            '{"tool": "create_task", "args": {"product_name": "嫩豆腐", "discount_rate": 0.8, "category": "daily_fresh", "original_stock": 50, "expiry_date": "2026-04-23"}, "reasoning": "创建出清任务", "continue": true}',
            '{"reasoning": "任务创建成功：嫩豆腐，折扣率 80%。请店长确认。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("帮我创建嫩豆腐的出清任务，打8折")

        assert result["success"] is True
        assert result["tool_name"] == "create_task"
        assert result["steps"] == 2

    @patch("app.services.agent_executor.get_minimax_llm")
    @patch("app.tools.registry.registry.dispatch")
    def test_executor_confirm_task_flow(self, mock_dispatch, mock_get_llm):
        """Test AgentExecutor routing to confirm_task"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_dispatch.return_value = {
            "success": True,
            "message": "任务已确认",
            "task_id": "test-task-123",
        }

        mock_llm.chat.side_effect = [
            '{"tool": "confirm_task", "args": {"task_id": "test-task-123", "confirmed_discount_rate": 0.4}, "reasoning": "确认出清任务", "continue": true}',
            '{"reasoning": "任务已确认，请员工执行扫描和价签打印。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("确认任务test-task-123，折扣40%")

        assert result["success"] is True
        assert result["tool_name"] == "confirm_task"
        assert result["steps"] == 2


class TestQueryPendingWithDiscountTool:
    """query_pending_with_discount combined tool tests"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.products_backup, self.tasks_backup = _backup_data()
        _setup_test_products()
        _clear_tasks()
        yield
        _restore_data(self.products_backup, self.tasks_backup)

    def test_query_pending_with_discount_returns_discount_info(self):
        """query_pending_with_discount should return products with discount recommendations"""
        import app.tools.store_tools
        from app.tools.registry import registry

        result = registry.dispatch(
            "query_pending_with_discount",
            args={"days_threshold": 7},
        )

        assert result["success"] is True
        assert result["count"] >= 1

        # Each product should have discount info
        for product in result["products"]:
            assert "recommended_discount" in product
            assert "days_left" in product