"""测试 webhook 路由 + FastAPI 生命周期（T5）。

webhook 是模拟端点（真实 POS/审批系统留 v2），但走完整 Action 治理链路。
测试用 TestClient + monkeypatch executor 指向临时数据，避免污染真实 data/。
"""
import json
import pytest
from fastapi.testclient import TestClient


def _setup_app(monkeypatch, data_dir):
    """构造一个指向临时数据的 app。

    monkeypatch _get_executor/_get_repo 指向 pack-based clearance executor，
    避免 vertical config 单 TTL 不完整的问题。
    """
    import importlib
    import os
    monkeypatch.setenv("QWEN_API_KEY", "stub")

    # 用 pack helper 构建完整 executor 指向临时数据
    from tests._clearance_helper import build_clearance_executor
    ex, repo = build_clearance_executor(data_dir)
    import engine.tools as T
    monkeypatch.setattr(T, "_get_executor", lambda vertical=None: ex)
    monkeypatch.setattr(T, "_get_repo", lambda tenant=None, vertical=None: repo)

    import main
    importlib.reload(main)
    client = TestClient(main.app)
    yield client, main


@pytest.fixture
def webhook_client(automation_data_dir, monkeypatch):
    yield from _setup_app(monkeypatch, automation_data_dir)


def test_health(webhook_client):
    """sanity: app 起得来，/health 200。"""
    client, _ = webhook_client
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_approval_webhook_approves_task(webhook_client):
    """POST /api/webhooks/approval → approve_clearance。

    需 pending_approval Task；automation_data_dir 没有，先经 executor 建一个。
    """
    client, main = webhook_client
    from engine.tools import _get_executor
    ex = _get_executor(vertical="clearance")
    # 建一个 task 并推到 pending_approval
    r = ex.execute("create_clearance_task", {
        "target_id": "nep_sold", "store_id": "store_001", "assignee_id": "emp_001",
        "discount_percent": 30, "planned_quantity": 5,
    }, actor={"role": "store_manager"}, tenant_id="tenant_default")
    task_id = r["created"]["Task"][0]["id"]
    ex.execute("submit_for_approval", {"task_id": task_id},
               actor={"role": "store_manager"}, tenant_id="tenant_default")

    resp = client.post("/api/webhooks/approval", json={
        "task_id": task_id, "approver_id": "rcm_1", "approved": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    task = ex.repo.read_one("Task", "tenant_default", task_id)
    assert task["status"] == "approved"


def test_pos_webhook_deducts_stock(webhook_client):
    """POST /api/webhooks/pos → deduct_stock。

    需 in_progress Task（deduct_stock 要求 task.status=in_progress）。
    automation_data_dir 的 task_exp 是 in_progress。
    """
    client, main = webhook_client
    from engine.tools import _get_executor
    ex = _get_executor(vertical="clearance")

    resp = client.post("/api/webhooks/pos", json={
        "target_id": "nep_exp", "task_id": "task_exp", "quantity": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    ne = ex.repo.read_one("NearExpiryProduct", "tenant_default", "nep_exp")
    assert ne["stock_quantity"] == 5  # 7 - 2
