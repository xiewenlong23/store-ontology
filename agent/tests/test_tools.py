from agent.tools import query_entity, confirm_action, execute_action
import agent.tools.shared as T


def _setup(monkeypatch, data_dir):
    from tests._clearance_helper import build_clearance_executor
    ex, repo = build_clearance_executor(data_dir)
    reg = repo.registry
    monkeypatch.setattr(T, "_parser", lambda vertical=None: type('P', (), {'registry': reg})())
    monkeypatch.setattr(T, "_get_repo", lambda tenant="jjy", vertical=None: repo)
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
    from agent.tools import update_task
    params = set(update_task.args)  # langchain StructuredTool.args
    forbidden = {"discount_percent", "status", "sold_quantity", "planned_quantity", "assignee_id"}
    assert not (params & forbidden), \
        f"update_task 不应接受受治理字段，实际签名含: {params & forbidden}"
    assert {"task_id", "notes", "priority"}.issubset(params)


def test_get_executor_default_resolves_workspace_from_contextvar():
    """_get_executor() 默认（无参）应从 tenant_ctx contextvar 解析 workspace，
    走 bootstrap_workspace 装配（spec §5.3 决策2）。不再依赖 vertical registry。

    判据：返回的 executor 与 bootstrap_workspace(workspace) 的 executor 是同一对象
    （同一缓存的 workspace 实例），而非 parser mode-3 临时新建的。"""
    from agent.tools import shared
    from engine.tenant import TenantContext
    from engine.workspace_bootstrap import bootstrap_workspace, reset_instances
    import main  # 提供 main.tenant_ctx contextvar

    reset_instances()
    token = main.tenant_ctx.set(TenantContext(workspace_name="jjy", org_unit_id="*"))
    try:
        ex = shared._get_executor()
        inst = bootstrap_workspace("jjy")
        # 同一 workspace 实例的 executor（缓存复用），而非临时新建
        assert ex is inst.executor, \
            "_get_executor() 默认应返回 bootstrap_workspace 缓存的 executor（workspace 装配）"
    finally:
        main.tenant_ctx.reset(token)
        reset_instances()
