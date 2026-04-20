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
