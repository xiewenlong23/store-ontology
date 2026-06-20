"""测试 webhook 路由 + FastAPI 生命周期（T5）。

webhook 是模拟端点（真实 POS/审批系统留 v2），但走完整 Action 治理链路。
测试用 TestClient + monkeypatch executor 指向临时数据，避免污染真实 data/。
"""
import json
import pytest
from fastapi.testclient import TestClient


def _setup_app(monkeypatch, data_dir):
    """构造一个指向临时数据的 app：替换 clearance executor 的 data_dir。

    用 importlib 重新 import main，让 TestClient 拿到带临时数据的 app。
    """
    import importlib
    import os
    monkeypatch.setenv("QWEN_API_KEY", "stub")
    from ontology import vertical as vertical_mod
    from ontology.parser import reset_parser_cache
    from verticals.clearance.config import CLEARANCE_CONFIG
    # 直接确保 clearance 已注册（bootstrap 可能因模块缓存未重注册）
    vertical_mod.register_vertical(CLEARANCE_CONFIG)
    reset_parser_cache()
    cfg = vertical_mod.get_vertical("clearance")
    original = cfg.data_dir
    cfg.data_dir = data_dir

    import main
    importlib.reload(main)
    client = TestClient(main.app)
    yield client, main

    cfg.data_dir = original
    reset_parser_cache()


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
    from ontology.tools import _get_executor
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
    from ontology.tools import _get_executor
    ex = _get_executor(vertical="clearance")

    resp = client.post("/api/webhooks/pos", json={
        "target_id": "nep_exp", "task_id": "task_exp", "quantity": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    ne = ex.repo.read_one("NearExpiryProduct", "tenant_default", "nep_exp")
    assert ne["stock_quantity"] == 5  # 7 - 2
