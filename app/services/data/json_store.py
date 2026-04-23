#!/usr/bin/env python3
"""
JSONDataService - Phase 1 JSON 文件存储实现

特性：
- fcntl 文件锁：读共享锁(LOCK_SH)，写排他锁(LOCK_EX)
- 上下文感知：自动从 ToolContext 获取 store_id
- 读缓存 + 失效策略：减少文件 I/O
- 线程安全：使用 ContextVar 存储上下文
"""

from __future__ import annotations

import fcntl
import json
import logging
import threading
from datetime import date
from pathlib import Path
from typing import Optional

from app.services.context import get_context
from app.services.data.base import DataService

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TASKS_FILE = DATA_DIR / "tasks.json"
PRODUCTS_FILE = DATA_DIR / "products.json"
STAFF_FILE = DATA_DIR / "staff.json"


class JSONDataService(DataService):
    """
    JSON 文件存储实现。

    文件结构：
    - products.json: 商品列表
    - tasks.json: 任务列表
    - staff.json: 员工列表

    每个文件都是完整的数组，load_* 返回时会按 store_id 过滤。
    """

    def __init__(self):
        # 缓存（进程内单例）
        self._products_cache: Optional[list[dict]] = None
        self._tasks_cache: Optional[list[dict]] = None
        self._staff_cache: Optional[list[dict]] = None
        self._cache_lock = threading.Lock()

    def _read_json(self, path: Path) -> list[dict]:
        """读取 JSON 文件（带共享锁）"""
        with open(path, encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _write_json(self, path: Path, data: list[dict]) -> None:
        """写入 JSON 文件（带排他锁）"""
        with open(path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2, default=str)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _get_effective_store_id(self, store_id: Optional[str]) -> str:
        """获取有效的 store_id：优先参数，否则从上下文"""
        if store_id:
            return store_id
        ctx = get_context()
        return ctx.store_id

    def load_products(self, store_id: Optional[str] = None) -> list[dict]:
        effective_store_id = self._get_effective_store_id(store_id)

        # 尝试从缓存读取
        with self._cache_lock:
            if self._products_cache is not None:
                return [p for p in self._products_cache if p.get("store_id") == effective_store_id]

        # 懒加载
        try:
            products = self._read_json(PRODUCTS_FILE)
        except FileNotFoundError:
            logger.warning(f"Products file not found: {PRODUCTS_FILE}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in products file: {e}")
            return []

        # 更新缓存
        with self._cache_lock:
            self._products_cache = products

        return [p for p in products if p.get("store_id") == effective_store_id]

    def save_products(self, products: list[dict]) -> None:
        self._write_json(PRODUCTS_FILE, products)
        # 失效缓存
        with self._cache_lock:
            self._products_cache = None

    def load_all_products(self) -> list[dict]:
        """加载所有商品（不过滤 store_id）"""
        with self._cache_lock:
            if self._products_cache is not None:
                return list(self._products_cache)

        try:
            products = self._read_json(PRODUCTS_FILE)
        except FileNotFoundError:
            logger.warning(f"Products file not found: {PRODUCTS_FILE}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in products file: {e}")
            return []

        with self._cache_lock:
            self._products_cache = products

        return list(products)

    def load_tasks(self, store_id: Optional[str] = None) -> list[dict]:
        effective_store_id = self._get_effective_store_id(store_id)

        # 尝试从缓存读取
        with self._cache_lock:
            if self._tasks_cache is not None:
                return [t for t in self._tasks_cache if t.get("store_id") == effective_store_id]

        # 懒加载
        try:
            tasks = self._read_json(TASKS_FILE)
        except FileNotFoundError:
            logger.warning(f"Tasks file not found: {TASKS_FILE}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in tasks file: {e}")
            return []

        # 更新缓存
        with self._cache_lock:
            self._tasks_cache = tasks

        return [t for t in tasks if t.get("store_id") == effective_store_id]

    def load_all_tasks(self) -> list[dict]:
        """加载所有任务（不过滤 store_id）"""
        with self._cache_lock:
            if self._tasks_cache is not None:
                return list(self._tasks_cache)

        try:
            tasks = self._read_json(TASKS_FILE)
        except FileNotFoundError:
            logger.warning(f"Tasks file not found: {TASKS_FILE}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in tasks file: {e}")
            return []

        with self._cache_lock:
            self._tasks_cache = tasks

        return list(tasks)

    def save_tasks(self, tasks: list[dict]) -> None:
        self._write_json(TASKS_FILE, tasks)
        # 失效缓存
        with self._cache_lock:
            self._tasks_cache = None

    # ── Staff ────────────────────────────────────────────────────

    def load_staff(self, store_id: Optional[str] = None) -> list[dict]:
        all_staff = self.load_all_staff()
        if store_id:
            return [s for s in all_staff if s.get("store_id") == store_id]
        return all_staff

    def load_all_staff(self) -> list[dict]:
        with self._cache_lock:
            if self._staff_cache is not None:
                return self._staff_cache
        try:
            with open(STAFF_FILE, encoding="utf-8") as f:
                staff_list = json.load(f)
        except Exception:
            staff_list = []
        with self._cache_lock:
            self._staff_cache = staff_list
        return staff_list

    def save_staff(self, staff: list[dict]) -> None:
        self._write_json(STAFF_FILE, staff)
        with self._cache_lock:
            self._staff_cache = None

    def invalidate_cache(self) -> None:
        """主动失效所有缓存"""
        with self._cache_lock:
            self._products_cache = None
            self._tasks_cache = None
            self._staff_cache = None
        logger.debug("DataService cache invalidated")
