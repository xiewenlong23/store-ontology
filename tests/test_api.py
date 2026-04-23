from fastapi.testclient import TestClient
from app.main import app
import json
from pathlib import Path

client = TestClient(app)

DATA_DIR = Path(__file__).parent.parent / "data"
TASKS_FILE = DATA_DIR / "tasks.json"

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_list_tasks_empty():
    r = client.get("/api/tasks/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_full_reduction_flow():
    # Backup original tasks.json
    with open(TASKS_FILE) as f:
        original_tasks = json.load(f)

    try:
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
        created_task = r.json()
        task_id = created_task["task_id"]

        # 4. Complete task with sell-through
        r = client.patch(f"/api/tasks/{task_id}/complete?sold_qty=40")
        assert r.status_code == 200
        assert r.json()["sell_through_rate"] == 0.8
    finally:
        # Restore original tasks.json for test isolation
        with open(TASKS_FILE, "w") as f:
            json.dump(original_tasks, f, indent=2, default=str)
