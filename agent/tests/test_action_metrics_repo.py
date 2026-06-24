"""ActionLogRepository.aggregate() 测试：JSON 后端必跑，PG 后端 skip-if-unavailable。

从 agent/ 跑：.venv/bin/pytest tests/test_action_metrics_repo.py -v
"""
import pytest

from engine.action_log import ActionLogEntry
from engine.action_log_repo import JSONFileActionLogRepository


# ============ 辅助 ============

def _entry(action_type="a", outcome="success", duration_ms=None,
           failure_type=None, ts="2026-06-20T10:00:00"):
    e = ActionLogEntry.init(action_type, {"user_id": "u1", "role": "r"},
                            "ws", "llm_session")
    e.outcome = outcome
    e.timestamp = ts
    e.duration_ms = duration_ms
    e.failure_type = failure_type
    return e


# ============ JSON 后端（必跑）============

def test_aggregate_empty_logs(tmp_path):
    """空 log → total=0，success_rate/p95 为 null，by_failure_type 全 0（8 类）。"""
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    m = repo.aggregate("ws")
    assert m["overall"]["total"] == 0
    assert m["overall"]["success_rate"] is None
    assert m["overall"]["p95_duration_ms"] is None
    assert sum(m["by_failure_type"].values()) == 0
    assert set(m["by_failure_type"].keys()) == {
        "unknown_action", "invalid_param", "permission_denied", "submission_failed",
        "entity_not_found", "illegal_transition", "side_effect_error", "unclassified"}
    assert m["by_action_type"] == {}


def test_aggregate_overall_counts(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("a", "success", duration_ms=10))
    repo.write(_entry("a", "success", duration_ms=20))
    repo.write(_entry("a", "failure", duration_ms=5, failure_type="invalid_param"))
    m = repo.aggregate("ws")
    assert m["overall"]["total"] == 3
    assert m["overall"]["success"] == 2
    assert m["overall"]["failure"] == 1
    assert m["overall"]["success_rate"] == round(2 / 3, 3)


def test_aggregate_p95_calculation(tmp_path):
    """5 条 duration [10,20,30,40,100]，P95 idx=ceil(0.95*5)-1=4 → 100。"""
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    for d in (10, 20, 30, 40, 100):
        repo.write(_entry("a", "success", duration_ms=d))
    m = repo.aggregate("ws")
    assert m["overall"]["p95_duration_ms"] == 100


def test_aggregate_by_action_type(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("create_clearance_task", "success", duration_ms=100))
    repo.write(_entry("create_clearance_task", "failure", duration_ms=5,
                     failure_type="invalid_param"))
    repo.write(_entry("deduct_stock", "success", duration_ms=15))
    m = repo.aggregate("ws")
    assert set(m["by_action_type"].keys()) == {"create_clearance_task", "deduct_stock"}
    cct = m["by_action_type"]["create_clearance_task"]
    assert cct["total"] == 2 and cct["success"] == 1 and cct["failure"] == 1
    assert cct["success_rate"] == 0.5


def test_aggregate_by_failure_type_counts_all_8_classes(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    for ft in ("invalid_param", "invalid_param", "permission_denied", "entity_not_found"):
        repo.write(_entry("a", "failure", duration_ms=5, failure_type=ft))
    m = repo.aggregate("ws")
    assert m["by_failure_type"]["invalid_param"] == 2
    assert m["by_failure_type"]["permission_denied"] == 1
    assert m["by_failure_type"]["entity_not_found"] == 1
    # 未出现的类为 0
    assert m["by_failure_type"]["side_effect_error"] == 0
    assert m["by_failure_type"]["unclassified"] == 0


def test_aggregate_window_filter(tmp_path):
    """since/until 过滤生效：窗口外的 log 不计入。"""
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("a", "success", duration_ms=10, ts="2026-06-01T00:00:00"))
    repo.write(_entry("a", "success", duration_ms=20, ts="2026-06-15T00:00:00"))
    m = repo.aggregate("ws", since="2026-06-10T00:00:00", until="2026-06-20T00:00:00")
    assert m["overall"]["total"] == 1  # 只有 06-15 那条在窗内


def test_aggregate_action_type_filter(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    repo.write(_entry("a", "success", duration_ms=10))
    repo.write(_entry("b", "success", duration_ms=20))
    m = repo.aggregate("ws", action_type="a")
    assert m["overall"]["total"] == 1
    assert list(m["by_action_type"].keys()) == ["a"]


def test_aggregate_window_in_response(tmp_path):
    repo = JSONFileActionLogRepository(data_dir=str(tmp_path), workspace_name="ws")
    m = repo.aggregate("ws", since="2026-06-01T00:00:00", until="2026-06-30T00:00:00")
    assert m["window"]["since"] == "2026-06-01T00:00:00"
    assert m["window"]["until"] == "2026-06-30T00:00:00"
