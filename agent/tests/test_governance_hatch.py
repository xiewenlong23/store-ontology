"""测试：关闭 edits-only 治理逃逸口（建模规范原则 7）。

问题：update_task（LLM 工具）用 bypass_action_check=True 改 Task，
治理逃逸口暴露在工具层。修复：Task 的 notes/priority 更新走受治理的
update_task_notes Action；bypass_action_check 只剩 executor 内部用。
"""
import inspect
import pytest

from agent.tools import update_task, execute_action
import agent.tools.shared as T


def _setup(monkeypatch, data_dir):
    from tests._clearance_helper import build_clearance_executor
    ex, repo = build_clearance_executor(data_dir)
    reg = repo.registry
    monkeypatch.setattr(T, "_parser", lambda vertical=None: type('P',(),{'registry':reg})())
    monkeypatch.setattr(T, "_get_repo", lambda tenant="jjy", vertical=None: repo)
    monkeypatch.setattr(T, "_get_executor", lambda vertical=None: ex)
    # v2（WP6）：actor 从 _get_actor 派生（auth_ctx → Employee → role）。
    # 测试环境无 auth_ctx，monkeypatch 模拟"当前用户是 store_manager"。
    monkeypatch.setattr(T, "_get_actor", lambda tenant=None: {"role": "store_manager"})
    # v2（WP5 接入）：PermissionEvaluator 求值；测试用空 evaluator（全 allow-by-default）
    # 让 store_manager 能调 update_task（submission_criteria 由 executor 校验）
    from engine.permission import PermissionEvaluator, _EmptyRegistry
    monkeypatch.setattr(T, "_get_evaluator",
                        lambda: PermissionEvaluator(registry=_EmptyRegistry(),
                                                    grants=[], tool_manifest={}))
    return ex, repo


def test_bypass_action_check_not_in_tools_layer():
    """原则7：bypass_action_check 只应出现在 executor 内部，不出现在 tools.py。"""
    tools_src = inspect.getsource(T)
    assert "bypass_action_check" not in tools_src, \
        "tools.py 不应含 bypass_action_check（治理逃逸口只在 executor 内部）"


def test_bypass_only_in_executor():
    """bypass_action_check 只在 executor.py 出现（执行器内部副作用写，是必要的）。"""
    from engine import executor as exec_mod
    assert "bypass_action_check" in inspect.getsource(exec_mod)


def test_update_task_notes_action_exists():
    """新增 update_task_notes Action：受治理的 notes/priority 更新。"""
    from engine.action_loader import load_actions
    from engine.bootstrap import bootstrap
    from tests._clearance_helper import build_clearance_registry
    bootstrap()
    reg = build_clearance_registry('.')
    actions = reg.action_types
    assert "update_task_notes" in actions, "应有 update_task_notes Action"


def test_update_task_notes_via_action(clearance_data_dir, monkeypatch):
    """update_task 工具改走 update_task_notes Action（不再 bypass）。"""
    ex, repo = _setup(monkeypatch, clearance_data_dir)
    # 先建一个 Task
    r = ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager"}, tenant_id="jjy")
    task_id = r["created"]["Task"][0]["id"]

    # 用 update_task 工具改 notes（应经 Action，不再 bypass）
    out = update_task.invoke({"task_id": task_id, "notes": "测试备注"})
    assert "成功" in out or "success" in out.lower(), f"应成功改 notes，实际: {out[:200]}"
    task = repo.read_one("Task", "jjy", task_id)
    assert task["notes"] == "测试备注"


def test_update_task_still_blocks_governed_fields(clearance_data_dir, monkeypatch):
    """update_task 签名不含 discount_percent/status 等——结构上无法传受治理字段。

    显式参数签名比白名单更强：受治理字段根本不在参数列表里，LLM 无法传入。
    """
    _setup(monkeypatch, clearance_data_dir)
    params = set(update_task.args)  # langchain StructuredTool.args = 接受的参数
    forbidden = {"discount_percent", "status", "sold_quantity", "planned_quantity", "assignee_id"}
    assert not (params & forbidden), \
        f"update_task 不应接受受治理字段，实际签名含: {params & forbidden}"
    assert {"task_id", "notes", "priority"}.issubset(params)
