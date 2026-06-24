"""E2E：跑一笔 clearance Action，验证完整链路：execute → 日志写入 → 可查询。

用 _clearance_helper 建真实 clearance executor + 注入 JSONFileActionLogRepo，
执行 create_clearance_task（success）+ 一个失败 Action（invalid_param），
断言 log_repo 有对应 success/failure entry，字段完整（affected_objects/failure_type 等）。
"""
import pytest

from engine.action_log_repo import JSONFileActionLogRepository
from tests._clearance_helper import build_clearance_executor


@pytest.fixture
def setup(clearance_data_dir):
    """建 executor + 注入 log_repo（指向独立 data_dir 避免污染）。"""
    ex, repo = build_clearance_executor(clearance_data_dir)
    log_repo = JSONFileActionLogRepository(data_dir=clearance_data_dir,
                                           workspace_name="jjy")
    ex.log_repo = log_repo
    return ex, repo, log_repo


def test_success_action_produces_log_entry(setup):
    """create_clearance_task 成功 → log 写入 success + affected_objects。"""
    ex, repo, log_repo = setup
    result = ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager", "id": "emp_001"},
       tenant_id="jjy", trigger_source="llm_session")

    assert result["ok"] is True
    entries = log_repo.query("jjy", action_type="create_clearance_task")
    assert len(entries) == 1
    e = entries[0]
    assert e.outcome == "success"
    assert e.failure_type is None
    assert e.trigger_source == "llm_session"
    assert e.actor_role == "store_manager"
    # create_clearance_task 建 Task + 改 NearExpiryProduct.status
    assert "Task" in e.affected_objects
    assert "NearExpiryProduct" in e.affected_objects
    assert e.duration_ms is not None and e.duration_ms >= 0


def test_failure_action_produces_failure_log_entry(setup):
    """discount 150（>100）→ invalid_param → log 记 failure + 重抛。"""
    ex, repo, log_repo = setup
    with pytest.raises(Exception):  # ValidationError
        ex.execute("create_clearance_task", {
            "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
            "discount_percent": 150, "planned_quantity": 50,
        }, actor={"role": "store_manager"}, tenant_id="jjy")

    entries = log_repo.query("jjy", outcome="failure")
    assert len(entries) == 1
    e = entries[0]
    assert e.outcome == "failure"
    assert e.failure_type == "invalid_param"
    assert "discount" in (e.error_message or "").lower() or "约束" in (e.error_message or "")
    assert e.affected_objects == {}  # 失败时无副作用


def test_multiple_actions_each_logged(setup):
    """连续跑多笔 Action，每笔都有独立 log entry。"""
    ex, repo, log_repo = setup
    # 第一笔成功
    r1 = ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager"}, tenant_id="jjy")
    task_id = r1["created"]["Task"][0]["id"]
    # 第二笔（submit_for_approval）
    ex.execute("submit_for_approval", {"task_id": task_id},
               actor={"role": "store_manager"}, tenant_id="jjy")

    all_entries = log_repo.query("jjy")
    assert len(all_entries) == 2
    action_types = {e.action_type for e in all_entries}
    assert action_types == {"create_clearance_task", "submit_for_approval"}


def test_count_after_actions(setup):
    """count 反映写入条数（为 admin API + 未来 Metrics 提供基础）。"""
    ex, repo, log_repo = setup
    ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager"}, tenant_id="jjy")
    assert log_repo.count("jjy") == 1
    assert log_repo.count("jjy", outcome="success") == 1
    assert log_repo.count("jjy", outcome="failure") == 0


def test_edits_object_types_populated_from_action(setup):
    """entry.edits_object_types 来自 Action 声明（spec §3.1；review I1 回归）。"""
    ex, repo, log_repo = setup
    ex.execute("create_clearance_task", {
        "target_id": "ne_001", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 50,
    }, actor={"role": "store_manager"}, tenant_id="jjy")
    e = log_repo.query("jjy", action_type="create_clearance_task")[0]
    # create_clearance_task 声明 edits NearExpiryProduct + Task
    assert "NearExpiryProduct" in e.edits_object_types
    assert "Task" in e.edits_object_types


def test_get_executor_by_process_name_injects_log_repo(clearance_data_dir, monkeypatch):
    """C1 回归：_get_executor(process_name=...) 构造的 executor 必须带 log_repo。

    否则 automation/webhook 路径（spec D2 要求覆盖的核心场景）不记日志。
    通过真实 bootstrap_workspace 路径验证，不 monkeypatch _get_executor。
    """
    from engine.workspace_bootstrap import bootstrap_workspace, invalidate_workspace
    from agent.tools import shared

    # 用真实 jjy workspace（已 bootstrap，log_repo 已注入 inst）
    invalidate_workspace("jjy")
    inst = bootstrap_workspace("jjy")
    assert inst.log_repo is not None, "bootstrap 应注入 log_repo"

    # 模拟 automation 经 _get_executor(process_name="clearance") 拿 executor
    monkeypatch.setattr(shared, "_parser", lambda: None)  # 避免 parser 重建
    # _get_executor 内部调 bootstrap_workspace + 取 process executor
    ex = shared._get_executor(process_name="clearance")
    assert ex.log_repo is not None, (
        "_get_executor(process_name=...) 构造的 executor 必须继承 inst.log_repo（C1）"
    )
