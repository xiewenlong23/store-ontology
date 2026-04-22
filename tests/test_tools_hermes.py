#!/usr/bin/env python3
"""
测试：Hermes 工具注册 + Agent Executor 多步工作流

迭代8改动：AgentExecutor 从单步改为多步循环
- LLM 输出 {tool, args, reasoning, continue} 决定下一步
- 工具执行结果注入对话历史，LLM 再决策
- 最多 MAX_STEPS 步自动结束

测试策略：
- mock LLM 多轮返回值（第一轮选工具，第二轮结束）
- mock handler 避免数据依赖
"""

import pytest
from unittest.mock import patch, MagicMock

# 触发工具注册
import app.tools.store_tools


class TestToolRegistryImport:
    """工具注册表导入测试（无变化）"""

    def test_store_tools_auto_registers_8_tools(self):
        from app.tools.registry import registry
        tools = registry.get_all_tools()

        expected = [
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
        actual = list(tools.keys())
        for name in expected:
            assert name in actual, f"Missing tool: {name} (have: {actual})"

    def test_tool_schema_has_required_fields(self):
        from app.tools.registry import registry, ToolEntry
        tools = registry.get_all_tools()

        for name, tool_entry in tools.items():
            assert isinstance(tool_entry, ToolEntry)
            assert hasattr(tool_entry, "schema")
            schema = tool_entry.schema
            assert isinstance(schema, dict)
            assert "name" in schema
            assert "description" in schema


class TestAgentExecutorMultiStep:
    """
    Agent Executor 多步循环测试。

    关键：mock 需要返回两轮：
    - 第一轮：返回工具调用，continue=True
    - 第二轮：返回最终回答，continue=False（结束循环）
    """

    @patch("app.services.agent_executor.get_minimax_llm")
    def test_routes_query_pending_products_two_steps(self, mock_get_llm):
        """
        测试两步流程：
        Step 1: LLM 选 query_pending_products，handler 返回数据
        Step 2: LLM 输出最终回答，continue=False
        """
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        # 第一轮：LLM 选择工具
        # 第二轮：LLM 输出最终回答（continue=False 表示结束）
        mock_llm.chat.side_effect = [
            # Step 1: 选工具
            '{"tool": "query_pending_products", "args": {}, "reasoning": "查询临期商品", "continue": true}',
            # Step 2: 结束
            '{"reasoning": "当前没有临期商品，库存都很新鲜。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("有哪些临期商品")

        assert result["success"] is True
        assert result["tool_name"] == "query_pending_products"
        assert result["steps"] == 2
        assert "没有临期" in result["response"]

    @patch("app.services.agent_executor.get_minimax_llm")
    @patch("app.tools.registry.registry.dispatch")
    def test_routes_query_tasks_two_steps(self, mock_dispatch, mock_get_llm):
        """测试查询任务的两步流程"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_dispatch.return_value = {
            "success": True,
            "count": 3,
            "tasks": [
                {"task_id": "T1", "status": "pending"},
                {"task_id": "T2", "status": "confirmed"},
                {"task_id": "T3", "status": "executed"},
            ],
        }

        mock_llm.chat.side_effect = [
            '{"tool": "query_tasks", "args": {}, "reasoning": "查询任务列表", "continue": true}',
            '{"reasoning": "当前共有3个任务，待确认1个，已确认1个，已执行1个。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("当前有哪些任务")

        assert result["success"] is True
        assert result["tool_name"] == "query_tasks"
        assert result["steps"] == 2
        mock_dispatch.assert_called_once()

    @patch("app.services.agent_executor.get_minimax_llm")
    @patch("app.tools.registry.registry.dispatch")
    def test_routes_create_task_two_steps(self, mock_dispatch, mock_get_llm):
        """测试创建任务的两步流程"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_dispatch.return_value = {
            "success": True,
            "task_id": "T-NEW-001",
            "message": "任务创建成功：嫩豆腐，折扣率 80%",
        }

        mock_llm.chat.side_effect = [
            '{"tool": "create_task", "args": {"product_name": "嫩豆腐", "discount_rate": 0.8, "category": "daily_fresh"}, "reasoning": "创建出清任务", "continue": true}',
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
    def test_routes_confirm_task_two_steps(self, mock_dispatch, mock_get_llm):
        """测试确认任务的两步流程"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_dispatch.return_value = {
            "success": True,
            "message": "任务已确认：嫩豆腐，折扣率 40%",
            "task_id": "T-001",
        }

        mock_llm.chat.side_effect = [
            '{"tool": "confirm_task", "args": {"task_id": "T-001", "confirmed_discount_rate": 0.4}, "reasoning": "确认出清任务", "continue": true}',
            '{"reasoning": "任务已确认：嫩豆腐，折扣率 40%。请员工执行扫描和价签打印。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("确认嫩豆腐的出清任务，折扣40%")

        assert result["success"] is True
        assert result["tool_name"] == "confirm_task"
        assert result["steps"] == 2

    @patch("app.services.agent_executor.get_minimax_llm")
    @patch("app.tools.registry.registry.dispatch")
    def test_routes_execute_task_two_steps(self, mock_dispatch, mock_get_llm):
        """测试执行任务的两步流程"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_dispatch.return_value = {
            "success": True,
            "message": "任务已执行：嫩豆腐",
            "task_id": "T-001",
        }

        mock_llm.chat.side_effect = [
            '{"tool": "execute_task", "args": {"task_id": "T-001"}, "reasoning": "执行出清任务", "continue": true}',
            '{"reasoning": "任务已执行：嫩豆腐。请店长复核售罄率。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("执行嫩豆腐的出清任务")

        assert result["success"] is True
        assert result["tool_name"] == "execute_task"
        assert result["steps"] == 2

    @patch("app.services.agent_executor.get_minimax_llm")
    @patch("app.tools.registry.registry.dispatch")
    def test_routes_review_task_two_steps(self, mock_dispatch, mock_get_llm):
        """测试复核任务的两步流程"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_dispatch.return_value = {
            "success": True,
            "message": "任务已复核：嫩豆腐，状态: 已完成",
            "task_id": "T-001",
            "final_status": "已完成",
        }

        mock_llm.chat.side_effect = [
            '{"tool": "review_task", "args": {"task_id": "T-001", "sell_through_rate": 0.95}, "reasoning": "复核任务", "continue": true}',
            '{"reasoning": "任务已复核：嫩豆腐，状态: 已完成。任务闭环。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("复核嫩豆腐的出清结果，售罄率95%")

        assert result["success"] is True
        assert result["tool_name"] == "review_task"
        assert result["steps"] == 2

    @patch("app.services.agent_executor.get_minimax_llm")
    @patch("app.tools.registry.registry.dispatch")
    def test_routes_query_discount_two_steps(self, mock_dispatch, mock_get_llm):
        """测试折扣查询的两步流程"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_dispatch.return_value = {
            "success": True,
            "recommended_discount": 0.4,
            "tier": 1,
            "tier_name": "TierShelfLife2to3Days",
            "reasoning": "剩余保质期2天，匹配Tier2，推荐折扣40%",
            "discount_range": [0.3, 0.6],
            "risk_level": "medium",
            "auto_confirm": False,
        }

        mock_llm.chat.side_effect = [
            '{"tool": "query_discount", "args": {"product_name": "嫩豆腐", "category": "daily_fresh", "expiry_date": "2026-04-23", "stock": 50}, "reasoning": "查询折扣建议", "continue": true}',
            '{"reasoning": "建议折扣率：40%（Tier2）。剩余保质期2天，匹配折扣规则，建议人工确认。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute(
            "嫩豆腐现在应该打几折",
            context={"product_name": "嫩豆腐", "category": "daily_fresh", "expiry_date": "2026-04-23", "stock": 50},
        )

        assert result["success"] is True
        assert result["tool_name"] == "query_discount"
        assert result["steps"] == 2

    @patch("app.services.agent_executor.get_minimax_llm")
    def test_unknown_intent_returns_failure(self, mock_get_llm):
        """测试未知意图返回 failure（LLM 无法决策，工具返回 None）"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        # LLM 返回无法理解的文本 → continue=False，直接作为回答
        mock_llm.chat.side_effect = [
            '{"reasoning": "抱歉，我暂时无法理解您的意思。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("这是一段完全无关的话 xyz123")

        assert result["success"] is False
        assert "无法理解" in result["response"]

    @patch("app.services.agent_executor.get_minimax_llm")
    @patch("app.tools.registry.registry.dispatch")
    def test_llm_recognizes_unknown_tool_and_retries(self, mock_dispatch, mock_get_llm):
        """
        测试 LLM 返回未知工具名时的处理：
        第一次返回 unknown_tool → 系统警告并继续
        第二次返回正确工具名
        第三次返回结束
        """
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_dispatch.return_value = {
            "success": True,
            "count": 5,
            "products": [
                {"name": "嫩豆腐", "days_left": 2, "stock": 50},
            ],
        }

        # 第一轮：LLM 返回不存在的工具名
        # 第二轮：LLM 返回正确的工具
        # 第三轮：LLM 输出最终回答
        mock_llm.chat.side_effect = [
            '{"tool": "fake_tool_xyz", "args": {}, "reasoning": "尝试调用", "continue": true}',
            '{"tool": "query_pending_products", "args": {}, "reasoning": "查询临期商品", "continue": true}',
            '{"reasoning": "当前有5件临期商品。", "continue": false}',
        ]

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("有哪些临期商品")

        assert result["success"] is True
        assert result["tool_name"] == "query_pending_products"
        assert result["steps"] == 3

    @patch("app.services.agent_executor.get_minimax_llm")
    def test_max_steps_prevents_infinite_loop(self, mock_get_llm):
        """
        测试 unknown_tool 次数限制：
        如果 LLM 每次都返回 continue=True 但工具名无效，
        循环会在 MAX_UNKNOWN_TOOL_RETRIES=2 次后强制结束。
        """
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        # 模拟 LLM 每次都返回无效工具，continue=True
        mock_llm.chat.return_value = '{"tool": "invalid_tool", "args": {}, "reasoning": "重试", "continue": true}'

        from app.services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        result = executor.execute("测试循环")

        # 应该在 MAX_UNKNOWN_TOOL_RETRIES=2 次后强制结束
        assert result["steps"] == 2
        assert result["tool_name"] is None  # 没有成功执行任何工具


class TestExplainDiscountReasoning:
    """解释型折扣查询测试（无变化）"""

    def test_explain_generates_natural_language(self):
        from app.services.ttl_llm_reasoning import explain_discount_reasoning

        result = explain_discount_reasoning(
            product_id="TEST-001",
            product_name="嫩豆腐",
            category="daily_fresh",
            expiry_date="2026-04-23",
            stock=80,
            discount_rate=0.4,
        )

        assert result["success"] is True
        assert "explanation" in result
        assert "嫩豆腐" in result["explanation"]
        assert result["discount_rate"] == 0.4

    def test_explain_without_discount_rate(self):
        from app.services.ttl_llm_reasoning import explain_discount_reasoning

        result = explain_discount_reasoning(
            product_id="TEST-002",
            product_name="测试商品",
            category="daily_fresh",
        )

        assert result["success"] is True
        assert "explanation" in result

    def test_explain_includes_ttl_rule_info(self):
        from app.services.ttl_llm_reasoning import explain_discount_reasoning

        result = explain_discount_reasoning(
            product_id="TEST-003",
            product_name="日配鲜奶",
            category="daily_fresh",
            expiry_date="2026-04-22",
            stock=120,
            discount_rate=0.3,
        )

        assert result["success"] is True
        assert "discount_range" in result or "recommended_discount" in result
