"""PostgreSQL 连接层 + schema 初始化（v2-存储 WP1/WP2，roadmap §1）。

设计：
- 单例连接池（psycopg 3 + psycopg-pool），启动时建，全进程复用
- ``DATABASE_URL`` 缺失时所有操作返回 None / 抛 PGNotConfigured（让上层回落 JSONFileRepository）
- ``migrate()`` 执行 ``sql/schema.sql``（幂等 CREATE IF NOT EXISTS）
- 事务上下文管理器 ``transaction()``：自动 commit/rollback
- 简单 ``execute(sql, params)`` / ``query(sql, params)`` helper

并发：psycopg-pool 维护连接池（默认 4-8 连接），每个 transaction 借一个连接。
"""
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

try:
    from psycopg import connect, sql, DatabaseError
    from psycopg_pool import ConnectionPool
    _HAS_PSYCOPG = True
except ImportError:  # pragma: no cover
    _HAS_PSYCOPG = False
    DatabaseError = Exception


class PGNotConfigured(RuntimeError):
    """DATABASE_URL 未配置；上层应回落 JSONFileRepository。"""


class PGNotAvailable(RuntimeError):
    """PG 配置了但连不上（实例未起/网络问题）。"""


# ============ 连接池单例 ============

_pool: Optional["ConnectionPool"] = None
_pool_lock = threading.Lock()
_pg_enabled: Optional[bool] = None   # 缓存"PG 是否启用"判断


def _get_database_url() -> Optional[str]:
    """从 env 读 DATABASE_URL；未配置返回 None。"""
    return os.getenv("DATABASE_URL")


def is_pg_enabled() -> bool:
    """PG 是否启用（DATABASE_URL 配置 + psycopg 可用）。

    结果缓存（不重复读 env）。测试可用 ``_reset_pg_state()`` 清缓存。
    """
    global _pg_enabled
    if _pg_enabled is None:
        _pg_enabled = bool(_HAS_PSYCOPG and _get_database_url())
    return _pg_enabled


def _reset_pg_state() -> None:
    """测试用：清缓存 + 关闭池。"""
    global _pool, _pg_enabled
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.close()
            except Exception:  # noqa: BLE001
                pass
        _pool = None
    _pg_enabled = None


def get_pool() -> "ConnectionPool":
    """获取连接池单例（首次调用时创建）。

    PG 未启用抛 PGNotConfigured；连接失败抛 PGNotAvailable。
    """
    global _pool
    if not _HAS_PSYCOPG:
        raise PGNotConfigured("psycopg 未安装")
    url = _get_database_url()
    if not url:
        raise PGNotConfigured("DATABASE_URL 未配置")

    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is None:
            try:
                # min_size=1 max_size=8（足够典型 web 并发；多 worker 时各进程一池）
                _pool = ConnectionPool(
                    conninfo=url, min_size=1, max_size=8,
                    open=True, timeout=10.0,
                )
            except Exception as e:  # noqa: BLE001
                raise PGNotAvailable(f"PG 连接失败：{e}") from e
    return _pool


# ============ 事务上下文 ============

@contextmanager
def transaction():
    """事务上下文管理器。

    用法：
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT ...")

    自动 commit（无异常）/ rollback（有异常）。
    """
    if not is_pg_enabled():
        raise PGNotConfigured("DATABASE_URL 未配置")
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ============ 简单 helper ============

def execute(sql_str: str, params: Optional[tuple] = None) -> int:
    """执行单条 SQL（INSERT/UPDATE/DELETE），返回 affected rowcount。

    PG 未启用抛 PGNotConfigured。
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_str, params or ())
            return cur.rowcount


def query(sql_str: str, params: Optional[tuple] = None) -> list[dict]:
    """执行查询，返回 list[dict]（每行 dict，列名 key）。"""
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_str, params or ())
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def query_one(sql_str: str, params: Optional[tuple] = None) -> Optional[dict]:
    """查询单行，无结果返回 None。"""
    rows = query(sql_str, params)
    return rows[0] if rows else None


# ============ migrate ============

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


def migrate() -> None:
    """执行 schema.sql（幂等，CREATE IF NOT EXISTS）。

    PG 未启用抛 PGNotConfigured。
    """
    if not is_pg_enabled():
        raise PGNotConfigured("DATABASE_URL 未配置")
    if not _SCHEMA_PATH.exists():
        raise FileNotFoundError(f"schema.sql 不存在：{_SCHEMA_PATH}")
    sql_text = _SCHEMA_PATH.read_text(encoding="utf-8")
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)


def ping() -> bool:
    """PG 连通性检查（不抛异常，返回 bool）。

    用于 health check / bootstrap 时判断 PG 是否可用。
    """
    if not is_pg_enabled():
        return False
    try:
        query_one("SELECT 1 AS ok")
        return True
    except (PGNotConfigured, PGNotAvailable, DatabaseError):
        return False
