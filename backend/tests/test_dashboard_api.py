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
