import time
from engine.preview_cache import PreviewCache


def test_store_and_retrieve():
    c = PreviewCache(ttl_seconds=60)
    pid = c.put({"action_type": "create_clearance_task", "target_id": "ne_1"})
    assert c.get(pid) == {"action_type": "create_clearance_task", "target_id": "ne_1"}


def test_get_consumes():
    c = PreviewCache(ttl_seconds=60)
    pid = c.put({"x": 1})
    c.get(pid)
    assert c.get(pid) is None  # 取走后失效


def test_expired_returns_none():
    c = PreviewCache(ttl_seconds=0)
    pid = c.put({"x": 1})
    time.sleep(0.01)
    assert c.get(pid) is None


def test_missing_returns_none():
    c = PreviewCache(ttl_seconds=60)
    assert c.get("nope") is None
