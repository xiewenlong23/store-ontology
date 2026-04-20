from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_list_tasks_empty():
    r = client.get("/api/tasks/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_full_reduction_flow():
    # 1. Agent scans products
    r = client.post("/api/reasoning/agent/scan")
    assert r.status_code == 200

    # 2. List tasks
    r = client.get("/api/tasks/")
    assert r.status_code == 200

    # 3. Create task
    r = client.post("/api/tasks/", json={
        "task_id": "T999",
        "store_id": "S001",
        "product_id": "P001",
        "product_name": "嫩豆腐",
        "category": "daily_fresh",
        "expiry_date": "2026-04-21",
        "original_stock": 50,
        "created_by": "agent"
    })
    assert r.status_code == 200

    # 4. Complete task with sell-through
    r = client.patch("/api/tasks/T999/complete?sold_qty=40")
    assert r.status_code == 200
    assert r.json()["sell_through_rate"] == 0.8
