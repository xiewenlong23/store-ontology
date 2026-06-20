"""preview 记录缓存（架构 spec §1.6）。confirm 必须持有效 preview_id。
MVP 进程内 dict + TTL；v2 可换 Redis。"""
import time
import uuid


class PreviewCache:
    def __init__(self, ttl_seconds: int = 300):
        self._store = {}  # preview_id -> (data, expire_at)
        self.ttl_seconds = ttl_seconds

    def put(self, data: dict) -> str:
        preview_id = f"pv_{uuid.uuid4().hex[:12]}"
        self._store[preview_id] = (data, time.time() + self.ttl_seconds)
        return preview_id

    def get(self, preview_id: str):
        entry = self._store.get(preview_id)
        if not entry:
            return None
        data, expire_at = entry
        if time.time() > expire_at:
            del self._store[preview_id]
            return None
        del self._store[preview_id]  # 取走即失效
        return data
