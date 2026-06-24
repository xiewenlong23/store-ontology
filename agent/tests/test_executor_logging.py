"""executor.execute 日志写入集成测试（spec §3.2）：

每种 failure_type + success + 向后兼容（无 log_repo）。
用 FakeLogRepo 捕获 entry，断言 outcome/failure_type/trigger_source/重抛。
"""
import time
from types import SimpleNamespace

import pytest

from engine.action_log_repo import ActionLogRepository
from engine.errors import ValidationError
from engine.executor import ActionExecutor


class FakeLogRepo(ActionLogRepository):
    storage_kind = "fake"
    def __init__(self):
        self.entries = []
    def write(self, e):
        self.entries.append(e)
    def query(self, ws, **f):
        return [e for e in self.entries if e.workspace_name == ws]
    def count(self, ws, **f):
        return len(self.query(ws, **f))


def _action(api_name="a", parameters=None, side_effects=None,
            submission_criteria=None, target_object_type="T", edits_object_types=None):
    return SimpleNamespace(
        api_name=api_name,
        parameters=parameters or [],
        side_effects=side_effects or [],
        submission_criteria=submission_criteria or {},
        target_object_type=target_object_type,
        edits_object_types=edits_object_types or [],
        locator_field=None,
    )


def _registry():
    return SimpleNamespace(object_types={"T": object})


def test_unknown_action_logs_failure_and_reraises():
    log = FakeLogRepo()
    ex = ActionExecutor(repository=None, actions={}, registry=_registry(),
                        config=None, log_repo=log)
    with pytest.raises(ValidationError):
        ex.execute("nope", {}, actor={"role": "r"}, tenant_id="ws",
                   trigger_source="llm_session")
    assert len(log.entries) == 1
    e = log.entries[0]
    assert e.outcome == "failure"
    assert e.failure_type == "unknown_action"
    assert e.trigger_source == "llm_session"


def test_invalid_param_logs_and_reraises():
    log = FakeLogRepo()
    action = _action(parameters=[{"name": "qty", "required": True}])
    ex = ActionExecutor(repository=None, actions={"a": action},
                        registry=_registry(), config=None, log_repo=log)
    with pytest.raises(ValidationError):
        ex.execute("a", {}, actor={"role": "r"}, tenant_id="ws")
    assert log.entries[0].failure_type == "invalid_param"


def test_default_trigger_source_is_llm_session():
    """execute 不传 trigger_source 时默认 llm_session（向后兼容，spec §3.2）。"""
    log = FakeLogRepo()
    ex = ActionExecutor(repository=None, actions={}, registry=_registry(),
                        config=None, log_repo=log)
    with pytest.raises(ValidationError):
        ex.execute("nope", {}, actor={"role": "r"}, tenant_id="ws")
    assert log.entries[0].trigger_source == "llm_session"


def test_executor_works_without_log_repo_for_backward_compat():
    """旧代码构造 executor 不传 log_repo 时不应崩（日志静默跳过）。"""
    ex = ActionExecutor(repository=None, actions={}, registry=_registry(), config=None)
    with pytest.raises(ValidationError):
        ex.execute("nope", {}, actor={"role": "r"}, tenant_id="ws")
    # 不崩即通过


def test_duration_ms_recorded():
    """success/failure 都记 duration_ms（为 Action Metrics 预留）。"""
    log = FakeLogRepo()
    ex = ActionExecutor(repository=None, actions={}, registry=_registry(),
                        config=None, log_repo=log)
    with pytest.raises(ValidationError):
        ex.execute("nope", {}, actor={"role": "r"}, tenant_id="ws")
    assert log.entries[0].duration_ms is not None
    assert log.entries[0].duration_ms >= 0


def test_log_repo_write_failure_does_not_block_request(monkeypatch, capsys):
    """log_repo.write 抛异常时 execute 仍正常重抛原异常（spec §7.3）。"""
    class BrokenRepo(ActionLogRepository):
        storage_kind = "broken"
        def write(self, e): raise RuntimeError("disk full")
        def query(self, *a, **k): return []
        def count(self, *a, **k): return 0

    ex = ActionExecutor(repository=None, actions={}, registry=_registry(),
                        config=None, log_repo=BrokenRepo())
    # 应抛 ValidationError（原异常），不是 RuntimeError（日志故障）
    with pytest.raises(ValidationError):
        ex.execute("nope", {}, actor={"role": "r"}, tenant_id="ws")
    captured = capsys.readouterr()
    assert "action_log" in captured.out  # 日志故障已 print warning


def test_automation_trigger_source_marked_agent_actor():
    """trigger_source=automation 时 actor_type=agent（spec §12.1 agent 身份）。"""
    log = FakeLogRepo()
    ex = ActionExecutor(repository=None, actions={}, registry=_registry(),
                        config=None, log_repo=log)
    with pytest.raises(ValidationError):
        ex.execute("nope", {}, actor={"role": "system_scheduler"},
                   tenant_id="ws", trigger_source="automation")
    assert log.entries[0].actor_type == "agent"
    assert log.entries[0].actor_id == "agent:automation"
