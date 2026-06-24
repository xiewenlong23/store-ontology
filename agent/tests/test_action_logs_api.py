"""admin action-logs API 测试（spec §6.1）：列表/详情/过滤/分页/权限。

用 FastAPI TestClient + monkeypatch require_admin 放行 + 注入 fake log_repo。
JWT_SECRET 由 conftest 设置；AUTH_REQUIRED 由 conftest 设 false。
"""
import pytest
from fastapi.testclient import TestClient

from engine.action_log import ActionLogEntry
from engine.action_log_repo import ActionLogRepository


class FakeRepo(ActionLogRepository):
    storage_kind = "fake"
    def __init__(self):
        self._e = []
    def write(self, e):
        self._e.append(e)
    def query(self, ws, **f):
        out = [e for e in self._e if e.workspace_name == ws]
        if f.get("action_type"):
            out = [e for e in out if e.action_type == f["action_type"]]
        if f.get("actor_id"):
            out = [e for e in out if e.actor_id == f["actor_id"]]
        if f.get("outcome"):
            out = [e for e in out if e.outcome == f["outcome"]]
        if f.get("failure_type"):
            out = [e for e in out if e.failure_type == f["failure_type"]]
        out.sort(key=lambda e: e.timestamp, reverse=True)
        limit = f.get("limit", 100)
        offset = f.get("offset", 0)
        return out[offset:offset + limit]
    def count(self, ws, **f):
        return len(self.query(ws, **{**f, "limit": 10**9, "offset": 0}))


@pytest.fixture
def client(monkeypatch):
    """放行 require_admin（返回 None）+ 拿 TestClient。

    patch 目标是 router 模块的 require_admin 引用（见 test_non_admin_denied 注释）。
    """
    monkeypatch.setattr("agent.routers.action_logs.require_admin", lambda ws, **kw: None)
    from agent.main import app
    return TestClient(app)


def test_list_action_logs_empty(client, monkeypatch):
    monkeypatch.setattr("agent.routers.action_logs._get_log_repo", lambda ws: FakeRepo())
    r = client.get("/api/admin/customers/jjy/action-logs")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_action_logs_returns_entries(client, monkeypatch):
    fake = FakeRepo()
    e = ActionLogEntry.init("create_clearance_task",
                            {"user_id": "u1", "role": "store_manager"},
                            "jjy", "llm_session")
    e.outcome = "success"
    e.affected_objects = {"Task": ["t1"]}
    fake._e.append(e)
    monkeypatch.setattr("agent.routers.action_logs._get_log_repo", lambda ws: fake)

    r = client.get("/api/admin/customers/jjy/action-logs")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["action_type"] == "create_clearance_task"
    assert item["outcome"] == "success"
    assert item["affected_objects"] == {"Task": ["t1"]}


def test_list_action_logs_filter_by_outcome(client, monkeypatch):
    fake = FakeRepo()
    for outcome in ("success", "failure"):
        e = ActionLogEntry.init("a", {"user_id": "u1", "role": "r"},
                                "jjy", "llm_session")
        e.outcome = outcome
        if outcome == "failure":
            e.failure_type = "invalid_param"
        fake._e.append(e)
    monkeypatch.setattr("agent.routers.action_logs._get_log_repo", lambda ws: fake)

    r = client.get("/api/admin/customers/jjy/action-logs?outcome=failure")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["outcome"] == "failure"


def test_detail_returns_full_entry(client, monkeypatch):
    fake = FakeRepo()
    e = ActionLogEntry.init("deduct_stock", {"user_id": "u1", "role": "system_pos"},
                            "jjy", "webhook")
    e.outcome = "success"
    e.params = {"quantity": 5}
    fake._e.append(e)
    monkeypatch.setattr("agent.routers.action_logs._get_log_repo", lambda ws: fake)

    r = client.get(f"/api/admin/customers/jjy/action-logs/{e.log_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["log_id"] == e.log_id
    assert body["params"] == {"quantity": 5}
    assert body["trigger_source"] == "webhook"


def test_detail_404_when_unknown(client, monkeypatch):
    monkeypatch.setattr("agent.routers.action_logs._get_log_repo", lambda ws: FakeRepo())
    r = client.get("/api/admin/customers/jjy/action-logs/nonexistent")
    assert r.status_code == 404


def test_non_admin_denied(monkeypatch):
    """require_admin 返回 403 时，路由应转发该响应（非放行）。

    注意：patch 目标是 router 模块的 require_admin 引用（router 顶部
    `from ... import require_admin` 已把符号绑到本模块命名空间，
    patch 源模块 engine.admin_ontology_api 不影响已 import 的别名）。
    """
    from fastapi.responses import JSONResponse

    def _deny(ws, **kw):
        return JSONResponse(status_code=403, content={"detail": "forbidden"})

    monkeypatch.setattr("agent.routers.action_logs.require_admin", _deny)
    monkeypatch.setattr("agent.routers.action_logs._get_log_repo", lambda ws: FakeRepo())
    from agent.main import app
    c = TestClient(app)
    r = c.get("/api/admin/customers/jjy/action-logs")
    assert r.status_code == 403
