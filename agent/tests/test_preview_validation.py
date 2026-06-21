"""测试：execute_action 预览阶段校验参数（冒烟发现的 bug 修复）。

冒烟现象：LLM 传了 near_expiry_product_id（错）而非 target_id（对），
预览成功（错误参数被存进缓存），confirm 时才报"缺少必填参数: target_id"，
导致 LLM 重试死循环。

修复：预览阶段就按 Action 契约校验参数，错误立即返回，不进缓存。
"""
from engine.tools import execute_action
from engine import tools as T


def _setup(monkeypatch, data_dir):
    """指向临时数据的 executor/repo 装配。"""
    from tests._clearance_helper import build_clearance_executor
    ex, repo = build_clearance_executor(data_dir)
    reg = repo.registry
    monkeypatch.setattr(T, "_parser", lambda vertical=None: type('P', (), {'registry': reg})())
    monkeypatch.setattr(T, "_get_repo", lambda tenant="tenant_default", vertical=None: repo)
    monkeypatch.setattr(T, "_get_executor", lambda vertical=None: ex)


def test_preview_rejects_wrong_param_name(clearance_data_dir, monkeypatch):
    """预览用错误参数名(near_expiry_product_id)应被拒，返回错误，不返回 preview_id。"""
    _setup(monkeypatch, clearance_data_dir)
    out = execute_action.invoke({
        "action_type": "create_clearance_task",
        "params": {"near_expiry_product_id": "ne_001",  # 错：应为 target_id
                   "store_id": "store_001", "assignee_id": "emp_001",
                   "discount_percent": 30, "planned_quantity": 50},
    })
    # 不应成功生成预览
    assert "preview_id" not in out, \
        f"错误参数名不应生成预览，实际返回: {out[:300]}"
    # 应提示正确的参数名
    assert "target_id" in out, \
        f"错误信息应提示正确参数名 target_id，实际: {out[:300]}"


def test_preview_accepts_correct_params_returns_preview_id(clearance_data_dir, monkeypatch):
    """预览用正确参数名(target_id)应成功，返回 preview_id。"""
    _setup(monkeypatch, clearance_data_dir)
    out = execute_action.invoke({
        "action_type": "create_clearance_task",
        "params": {"target_id": "ne_001", "store_id": "store_001",
                   "assignee_id": "emp_001", "discount_percent": 30, "planned_quantity": 50},
    })
    assert "preview_id" in out, f"正确参数应生成预览，实际: {out[:300]}"
