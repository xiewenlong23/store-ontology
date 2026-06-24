"""admin action-metrics API 测试（spec §3.1/§3.2）：鉴权/空响应/有数据/过滤/默认窗。

JWT_SECRET 由 conftest 设；AUTH_REQUIRED 由 conftest 设 false。
patch 目标是 router 模块别名（与 test_action_logs_api 一致）。
"""
import pytest
from fastapi.testclient import TestClient


EMPTY_AGG = {
    "window": {"since": None, "until": None},
    "filters": {"action_type": None, "trigger_source": None},
    "overall": {"total": 0, "success": 0, "failure": 0,
                "success_rate": None, "p95_duration_ms": None},
    "by_action_type": {},
    "by_failure_type": {ft: 0 for ft in (
        "unknown_action", "invalid_param", "permission_denied", "submission_failed",
        "entity_not_found", "illegal_transition", "side_effect_error", "unclassified")},
}


class FakeRepo:
    """复用 aggregate 返回值，不依赖真实存储。"""
    storage_kind = "fake"
    def __init__(self, agg_result=EMPTY_AGG):
        self._agg = agg_result
    def aggregate(self, ws, **kw):
        return self._agg


class CaptureRepo:
    """捕获 aggregate 调用的 kwargs，返回空 agg。"""
    storage_kind = "fake"
    def __init__(self):
        self.captured = {}
    def aggregate(self, ws, **kw):
        self.captured.update(kw)
        return EMPTY_AGG


@pytest.fixture
def client(monkeypatch):
    """放行 require_admin（patch router 模块别名）。"""
    monkeypatch.setattr("agent.routers.action_metrics.require_admin",
                        lambda ws, **kw: None)
    from agent.main import app
    return TestClient(app)


def test_metrics_empty(client, monkeypatch):
    monkeypatch.setattr("agent.routers.action_metrics._get_log_repo",
                        lambda ws: FakeRepo())
    r = client.get("/api/admin/customers/jjy/action-metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"]["total"] == 0
    assert body["overall"]["success_rate"] is None
    assert len(body["by_failure_type"]) == 8


def test_metrics_with_data(client, monkeypatch):
    agg = dict(EMPTY_AGG)
    agg["overall"] = {"total": 3, "success": 2, "failure": 1,
                      "success_rate": 0.667, "p95_duration_ms": 100}
    agg["by_action_type"] = {"create_clearance_task": {
        "total": 3, "success": 2, "failure": 1, "success_rate": 0.667,
        "p95_duration_ms": 100}}
    monkeypatch.setattr("agent.routers.action_metrics._get_log_repo",
                        lambda ws: FakeRepo(agg))
    r = client.get("/api/admin/customers/jjy/action-metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"]["total"] == 3
    assert "create_clearance_task" in body["by_action_type"]


def test_metrics_passes_query_params(client, monkeypatch):
    """since/until/action_type/trigger_source 透传到 aggregate。"""
    cap = CaptureRepo()
    monkeypatch.setattr("agent.routers.action_metrics._get_log_repo", lambda ws: cap)
    r = client.get("/api/admin/customers/jjy/action-metrics"
                   "?since=2026-06-01&until=2026-06-30&action_type=create&trigger_source=automation")
    assert r.status_code == 200
    assert cap.captured["since"] == "2026-06-01"
    assert cap.captured["until"] == "2026-06-30"
    assert cap.captured["action_type"] == "create"
    assert cap.captured["trigger_source"] == "automation"


def test_metrics_default_window_30_days(client, monkeypatch):
    """不传 since 时默认 30 天前（spec M2）；精确断言 ~30 天差，防回归成 7 天。"""
    from datetime import datetime, timedelta
    cap = CaptureRepo()
    monkeypatch.setattr("agent.routers.action_metrics._get_log_repo", lambda ws: cap)
    now_before = datetime.now()
    r = client.get("/api/admin/customers/jjy/action-metrics")
    assert r.status_code == 200
    until_dt = datetime.fromisoformat(cap.captured["until"])
    since_dt = datetime.fromisoformat(cap.captured["since"])
    # until ≈ now（请求时刻）
    assert abs((until_dt - now_before).total_seconds()) < 5
    # since ≈ now - 30 天（容差 5 秒）
    expected_since = now_before - timedelta(days=30)
    assert abs((since_dt - expected_since).total_seconds()) < 5


def test_metrics_non_admin_denied(monkeypatch):
    """require_admin 返回 403 时路由转发（patch router 模块别名）。"""
    from fastapi.responses import JSONResponse
    monkeypatch.setattr("agent.routers.action_metrics.require_admin",
                        lambda ws, **kw: JSONResponse(status_code=403,
                                                      content={"detail": "forbidden"}))
    monkeypatch.setattr("agent.routers.action_metrics._get_log_repo",
                        lambda ws: FakeRepo())
    from agent.main import app
    c = TestClient(app)
    r = c.get("/api/admin/customers/jjy/action-metrics")
    assert r.status_code == 403
