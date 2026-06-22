"""WP5 defer 落地：submission_criteria 操作符全集测试。

验证设计文档 §5（v2-权限 defer 项）：
  - is / is_not（原有）
  - gte / lte / gt / lt（数值比较）
  - matches（正则）
  - includes（list/str 包含）
  - value_ref（actual == params[other_field]）
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from engine.executor import _eval_operator, _eval_condition_with_params


class TestIsOperators:

    def test_is_equal(self):
        assert _eval_operator("is", "approved", "approved") is True
        assert _eval_operator("is", "approved", "rejected") is False

    def test_is_not(self):
        assert _eval_operator("is_not", "approved", "rejected") is True
        assert _eval_operator("is_not", "approved", "approved") is False

    def test_is_none_handling(self):
        assert _eval_operator("is", None, None) is True
        assert _eval_operator("is", None, "x") is False


class TestNumericOperators:

    def test_gte(self):
        assert _eval_operator("gte", 100, 50) is True
        assert _eval_operator("gte", 50, 50) is True
        assert _eval_operator("gte", 30, 50) is False

    def test_lte(self):
        assert _eval_operator("lte", 30, 50) is True
        assert _eval_operator("lte", 50, 50) is True
        assert _eval_operator("lte", 100, 50) is False

    def test_gt_lt(self):
        assert _eval_operator("gt", 51, 50) is True
        assert _eval_operator("gt", 50, 50) is False
        assert _eval_operator("lt", 49, 50) is True
        assert _eval_operator("lt", 50, 50) is False

    def test_numeric_string_coercion(self):
        """字符串数字也应能比较（如 '100' gte 50）。"""
        assert _eval_operator("gte", "100", 50) is True
        assert _eval_operator("lt", "30", 50) is True

    def test_non_numeric_returns_false(self):
        """非数字字段做数值比较 → False（保守不通过）。"""
        assert _eval_operator("gte", "abc", 50) is False

    def test_none_returns_false(self):
        """actual 为 None 做数值比较 → False。"""
        assert _eval_operator("gte", None, 50) is False


class TestMatchesOperator:

    def test_matches_basic(self):
        assert _eval_operator("matches", "abc123", r"\d+") is True
        assert _eval_operator("matches", "no digits", r"\d+") is False

    def test_matches_anchored(self):
        """默认 re.search（部分匹配）。"""
        assert _eval_operator("matches", "status: approved", r"approved") is True

    def test_matches_invalid_regex(self):
        """非法正则 → False（不抛）。"""
        assert _eval_operator("matches", "x", r"[invalid") is False

    def test_matches_none(self):
        assert _eval_operator("matches", None, r"x") is False


class TestIncludesOperator:

    def test_includes_in_list(self):
        assert _eval_operator("includes", ["a", "b", "c"], "b") is True
        assert _eval_operator("includes", ["a", "b"], "z") is False

    def test_includes_in_string(self):
        assert _eval_operator("includes", "hello world", "world") is True
        assert _eval_operator("includes", "hello", "world") is False

    def test_includes_in_dict_key(self):
        assert _eval_operator("includes", {"a": 1, "b": 2}, "a") is True

    def test_includes_none(self):
        assert _eval_operator("includes", None, "x") is False


class TestValueRefOperator:

    def test_value_ref_basic(self):
        """value_ref: actual 应等于 params[other_field]。"""
        cond = {"operator": "value_ref", "value": "$target_id"}
        # actual=42, params.target_id=42 → True
        assert _eval_condition_with_params(cond, 42, {"target_id": 42}) is True
        # actual=42, params.target_id=99 → False
        assert _eval_condition_with_params(cond, 42, {"target_id": 99}) is False

    def test_value_ref_missing_param(self):
        """params 缺字段 → False（不抛）。"""
        cond = {"operator": "value_ref", "value": "$missing"}
        assert _eval_condition_with_params(cond, "x", {}) is False

    def test_value_ref_invalid_format(self):
        """value 不是 $xxx 形式 → False。"""
        cond = {"operator": "value_ref", "value": "literal"}
        assert _eval_condition_with_params(cond, "literal", {}) is False


class TestUnknownOperator:

    def test_unknown_returns_false(self):
        """未知操作符 → False（保守拒绝）。"""
        assert _eval_operator("bogus", "x", "y") is False


# ============ 端到端：通过 ActionExecutor 验证 ============

class TestExecutorUsesNewOperators:
    """验证 executor._check_submission 真的用新操作符。"""

    def _build_executor(self, conditions, target=None):
        from engine.executor import ActionExecutor
        from engine.action_loader import ActionDefinition
        from engine.repository import JSONFileRepository
        from engine.parser import EntityRegistry
        from engine.state_machine import TASK_TRANSITIONS, TERMINAL_STATES
        from engine.pack import ValueChainProcess

        action = ActionDefinition(
            api_name="test_action", display_name="t", description="test",
            status="active",
            target_object_type="Task", edits_object_types=["Task"],
            parameters=[{"name": "task_id", "type": "string", "required": True}],
            submission_criteria={"roles": [], "conditions": conditions},
            side_effects=[], locator_field="task_id")

        class _Reg:
            object_types = {}
            link_types = {}
            action_types = {"test_action": action}
        class _Repo:
            def read_one(self, et, tc, eid):
                return target if target else {"id": eid, "status": "in_progress", "qty": 50}
        proc = ValueChainProcess(
            name="t", display_name="t", workflow_object_type="Task",
            workflow_object_id_field="task_id",
            state_transitions=TASK_TRANSITIONS, terminal_states=list(TERMINAL_STATES))
        return ActionExecutor(repository=_Repo(), actions={"test_action": action},
                              registry=_Reg(), config=proc)

    def test_gte_passes(self):
        """qty >= 10 通过（qty=50）。"""
        ex = self._build_executor(
            [{"field": "target.qty", "operator": "gte", "value": 10, "fail_msg": "qty 不足"}])
        # 不抛即通过
        ex._check_submission(
            ex.actions["test_action"], {"role": "any"},
            target={"id": "t1", "status": "x", "qty": 50},
            params={"task_id": "t1"}, tenant_id="jjy")

    def test_gte_fails_with_msg(self):
        from engine.errors import ValidationError
        ex = self._build_executor(
            [{"field": "target.qty", "operator": "gte", "value": 100, "fail_msg": "qty 不足 100"}])
        with pytest.raises(ValidationError, match="qty 不足 100"):
            ex._check_submission(
                ex.actions["test_action"], {"role": "any"},
                target={"id": "t1", "status": "x", "qty": 50},
                params={"task_id": "t1"}, tenant_id="jjy")

    def test_matches_in_action(self):
        """status matches 正则 in_progress|approved。"""
        ex = self._build_executor(
            [{"field": "target.status", "operator": "matches",
              "value": "in_progress|approved", "fail_msg": "状态不在合法集"}])
        ex._check_submission(
            ex.actions["test_action"], {"role": "any"},
            target={"id": "t1", "status": "in_progress"},
            params={"task_id": "t1"}, tenant_id="jjy")  # 不抛即通过
