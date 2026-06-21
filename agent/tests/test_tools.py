from engine.tools import query_entity, confirm_action, execute_action
from engine import tools as T


def _setup(monkeypatch, data_dir):
    from tests._clearance_helper import build_clearance_executor
    ex, repo = build_clearance_executor(data_dir)
    reg = repo.registry
    monkeypatch.setattr(T, "_parser", lambda vertical=None: type('P', (), {'registry': reg})())
    monkeypatch.setattr(T, "_get_repo", lambda tenant="tenant_default", vertical=None: repo)
    monkeypatch.setattr(T, "_get_executor", lambda vertical=None: ex)


def test_query_entity_reads_store(clearance_data_dir, monkeypatch):
    _setup(monkeypatch, clearance_data_dir)
    out = query_entity.invoke({"entity_type": "Store"})
    assert "store_001" in out


def test_execute_action_returns_preview_id(clearance_data_dir, monkeypatch):
    _setup(monkeypatch, clearance_data_dir)
    out = execute_action.invoke({
        "action_type": "create_clearance_task",
        "params": {"target_id": "ne_001", "store_id": "store_001",
                   "assignee_id": "emp_001", "discount_percent": 30, "planned_quantity": 50}})
    assert "preview_id" in out


def test_confirm_requires_preview(clearance_data_dir, monkeypatch):
    _setup(monkeypatch, clearance_data_dir)
    out = confirm_action.invoke({"preview_id": "bogus"})
    assert "preview" in out.lower() or "失败" in out or "无效" in out


def test_update_task_blocks_governed_fields(clearance_data_dir, monkeypatch):
    """回归：update_task 签名不含受治理字段（结构上无法传 discount_percent/status 等）。

    显式参数签名比运行时白名单更强——受治理字段根本不在参数列表里。
    """
    _setup(monkeypatch, clearance_data_dir)
    from engine.tools import update_task
    params = set(update_task.args)  # langchain StructuredTool.args
    forbidden = {"discount_percent", "status", "sold_quantity", "planned_quantity", "assignee_id"}
    assert not (params & forbidden), \
        f"update_task 不应接受受治理字段，实际签名含: {params & forbidden}"
    assert {"task_id", "notes", "priority"}.issubset(params)
