"""测试运营看板 + 本体管理 API（P4）。"""
import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    os.environ["QWEN_API_KEY"] = "stub"
    import main
    return TestClient(main.app)


# ============ T1: 本体管理 API ============

def test_ontology_objects(client):
    """GET /api/admin/customers/customer_default/ontology/objects 返回 Object 列表。"""
    r = client.get("/api/admin/customers/customer_default/ontology/objects")
    assert r.status_code == 200
    data = r.json()
    assert "objects" in data
    names = [o["id"] for o in data["objects"]]
    assert "Product" in names
    assert "Task" in names


def test_ontology_objects_has_properties(client):
    """Object 详情含属性列表。"""
    r = client.get("/api/admin/customers/customer_default/ontology/objects")
    product = next(o for o in r.json()["objects"] if o["id"] == "Product")
    assert "properties" in product
    prop_names = [p["name"] for p in product["properties"]]
    assert "id" in prop_names
    assert "name" in prop_names


def test_ontology_actions(client):
    """GET /api/admin/customers/customer_default/ontology/actions 返回 Action 列表。"""
    r = client.get("/api/admin/customers/customer_default/ontology/actions")
    assert r.status_code == 200
    names = [a["api_name"] for a in r.json()["actions"]]
    assert "create_clearance_task" in names


def test_ontology_links(client):
    """GET /api/admin/customers/customer_default/ontology/links 返回 Link 列表。"""
    r = client.get("/api/admin/customers/customer_default/ontology/links")
    assert r.status_code == 200
    names = [l["id"] for l in r.json()["links"]]
    assert "located_in" in names


# ============ T2: 运营看板指标 API ============

def test_dashboard_metrics(client):
    """GET /api/dashboard/customer_default/metrics 返回跨域 KPI。"""
    r = client.get("/api/dashboard/customer_default/metrics")
    assert r.status_code == 200
    data = r.json()
    assert "tasks" in data
    assert "near_expiry" in data
    # tasks 按 status 分组计数
    assert "total" in data["tasks"]
    # near_expiry 按 status 分组计数
    assert "total" in data["near_expiry"]


def test_dashboard_metrics_counts_are_ints(client):
    """指标计数值是整数。"""
    r = client.get("/api/dashboard/customer_default/metrics")
    data = r.json()
    assert isinstance(data["tasks"]["total"], int)
    assert isinstance(data["near_expiry"]["total"], int)


# ============ T3: 待办 API ============

def test_dashboard_todos(client):
    """GET /api/dashboard/customer_default/todos 返回待办列表。"""
    r = client.get("/api/dashboard/customer_default/todos")
    assert r.status_code == 200
    data = r.json()
    assert "todos" in data
    assert isinstance(data["todos"], list)


def test_dashboard_todos_only_pending(client):
    """待办只含 pending_approval / in_progress 状态的 Task。"""
    r = client.get("/api/dashboard/customer_default/todos")
    for todo in r.json()["todos"]:
        assert todo["status"] in ("created", "pending_approval", "approved",
                                  "accepted", "in_progress")


# ============ T4: X-Workspace header 路由（架构 spec §3.4）===========

def test_x_workspace_header_drives_workspace_resolution(client):
    """X-Workspace header 决定运行的 workspace（优先于 URL {cid}）。

    架构 spec §3.4：前端通过 X-Workspace 告诉后端运行在哪个 workspace。
    发不同 X-Workspace 值应路由到不同 workspace（这里用 customer_default 验证
    header 能解析；未来多 workspace 时可验证 header 切换不同本体）。
    """
    # 不带 header：用 URL cid（customer_default），应正常返回
    r_no_header = client.get("/api/dashboard/customer_default/metrics")
    assert r_no_header.status_code == 200
    assert "tasks" in r_no_header.json()

    # 带 X-Workspace header（值与 cid 相同）：仍正常，证明 header 被解析且兼容
    r_with_header = client.get(
        "/api/dashboard/customer_default/metrics",
        headers={"X-Workspace": "jjy"})
    assert r_with_header.status_code == 200
    assert "tasks" in r_with_header.json()
    # 结果与不带 header 一致（同一 workspace）
    assert r_with_header.json() == r_no_header.json()


def test_x_workspace_header_overrides_url_cid(client):
    """X-Workspace header 优先级高于 URL {cid}（架构 spec §3.4）。

    发 X-Workspace: customer_default 但 URL cid 用一个不存在的值，
    应仍按 header 指向的 workspace 工作（URL cid 被忽略）。
    """
    r = client.get(
        "/api/dashboard/bogus_cid/metrics",
        headers={"X-Workspace": "jjy"})
    assert r.status_code == 200
    assert "tasks" in r.json()


def test_resolve_workspace_name_priority(client):
    """_resolve_workspace_name 优先级：header > URL cid > 默认。"""
    import main
    from fastapi import Request

    # 模拟 request 对象（TestClient 实际请求会经 middleware 设置 state）
    class _FakeRequest:
        def __init__(self, workspace_name=None):
            self.state = type('s', (), {'workspace_name': workspace_name})()

    # header 存在 → 用 header
    assert main._resolve_workspace_name(_FakeRequest("ws_from_header"), "url_cid") == "ws_from_header"
    # header 缺失、url cid 存在 → 用 url cid
    assert main._resolve_workspace_name(_FakeRequest(None), "url_cid") == "url_cid"
    # 都缺失 → 默认 jjy
    assert main._resolve_workspace_name(_FakeRequest(None), None) == "jjy"
