# ============================================================
# 审计服务 — Phase 5.1
# 将 Agent 调用、工具执行、HITL 审批写入 PostgreSQL
# ============================================================
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional
import structlog
from app.audit.logger import get_logger
from app.config import settings

log = get_logger("audit")

# ============================================================
# PostgreSQL 写入（生产环境）
# ============================================================
async def write_audit_log(
    session_id: str,
    user_id: str,
    store_id: str,
    action: str,
    payload: dict,
    duration_ms: int = None,
    model: str = None,
) -> bool:
    """
    将审计日志写入 PostgreSQL
    失败时降级到文件日志，不阻塞主流程
    """
    if not settings.database_url:
        await _write_audit_log_file(session_id, user_id, store_id, action, payload, duration_ms, model)
        return False

    try:
        import asyncpg
        conn = await asyncpg.connect(settings.database_url)

        # 计算防篡改 hash
        payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        hash_input = f"{payload_str}{settings.audit_secret_key}"
        output_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        await conn.execute(
            """
            INSERT INTO audit_log (session_id, user_id, store_id, action, payload, output_hash, duration_ms, model)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
            """,
            session_id, user_id, store_id, action,
            json.dumps(payload, sort_keys=True, ensure_ascii=False),
            output_hash, duration_ms, model,
        )
        await conn.close()
        return True
    except Exception as e:
        log.error("审计日志写入PostgreSQL失败，降级到文件", error=str(e))
        await _write_audit_log_file(session_id, user_id, store_id, action, payload, duration_ms, model)
        return False


# ============================================================
# 文件写入（测试环境）
# ============================================================
import asyncio
import aiofiles
import os

AUDIT_LOG_FILE = os.environ.get("AUDIT_LOG_FILE", "/tmp/audit.log")


async def _write_audit_log_file(
    session_id: str,
    user_id: str,
    store_id: str,
    action: str,
    payload: dict,
    duration_ms: int = None,
    model: str = None,
) -> None:
    """审计日志降级写入文件"""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "user_id": user_id,
        "store_id": store_id,
        "action": action,
        "payload": payload,
        "duration_ms": duration_ms,
        "model": model,
    }
    try:
        async with aiofiles.open(AUDIT_LOG_FILE, mode="a") as f:
            await f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.error("审计日志写入文件也失败", error=str(e), entry=entry)


# ============================================================
# HITL 审批记录
# ============================================================
async def write_hitl_approval(
    task_id: str,
    task_type: str,
    approver_id: str,
    approver_role: str,
    decision: str,
    original_params: dict = None,
    final_params: dict = None,
    rejection_reason: str = None,
    comment: str = None,
) -> bool:
    """
    将 HITL 审批记录写入 PostgreSQL
    字段名与 TECH 10.1 保持一致：task_type（discount/task/display）
    """
    if not settings.database_url:
        log.warning("HITL审批记录：database_url未配置，跳过写入", task_id=task_id)
        return False

    try:
        import asyncpg
        conn = await asyncpg.connect(settings.database_url)

        # 防篡改 hash
        raw = json.dumps({"task_id": task_id, "task_type": task_type,
                           "decision": decision}, sort_keys=True)
        payload_hash = hashlib.sha256(
            f"{raw}{settings.audit_secret_key}".encode()
        ).hexdigest()

        await conn.execute(
            """
            INSERT INTO hitl_approval
                (task_id, task_type, approver_id, approver_role, decision,
                 original_params, final_params, rejection_reason, payload_hash, comment)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9, $10)
            """,
            task_id, task_type, approver_id, approver_role, decision,
            json.dumps(original_params) if original_params else None,
            json.dumps(final_params) if final_params else None,
            rejection_reason, payload_hash, comment,
        )
        await conn.close()
        return True
    except Exception as e:
        log.error("HITL审批记录写入失败", error=str(e), task_id=task_id)
        return False


# ============================================================
# 工具执行审计装饰器
# ============================================================
import asyncio
import time
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def audited_tool(tool_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    工具执行审计装饰器
    支持 async 和 sync 函数，自动处理协程

    用法：
        @audited_tool("query_expiring_products")
        async def query_expiring_products(...):
            ...

    注意：被装饰函数如果接受 AgentState，请确保 state 参数名或位置固定，
         或者从 kwargs 中按名称提取（当前实现从 kwargs.get("state") 提取）
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.monotonic()
            state = kwargs.get("state") or (args[0] if args and hasattr(args[0], "get") else None)
            session_id = _get_state_field(state, "session_id")
            user_id = _get_state_field(state, "user_id")
            store_id = _get_state_field(state, "store_id")

            try:
                result = await func(*args, **kwargs)
                duration_ms = int((time.monotonic() - start) * 1000)
                _audit_async(
                    session_id, user_id, store_id,
                    f"tool:{tool_name}",
                    {"args": str(args), "kwargs": str(kwargs), "result": "success"},
                    duration_ms,
                )
                return result
            except Exception as e:
                duration_ms = int((time.monotonic() - start) * 1000)
                _audit_async(
                    session_id, user_id, store_id,
                    f"tool:{tool_name}:error",
                    {"args": str(args), "kwargs": str(kwargs), "error": str(e)},
                    duration_ms,
                )
                raise

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.monotonic()
            state = kwargs.get("state") or (args[0] if args and hasattr(args[0], "get") else None)
            session_id = _get_state_field(state, "session_id")
            user_id = _get_state_field(state, "user_id")
            store_id = _get_state_field(state, "store_id")

            try:
                result = func(*args, **kwargs)
                # sync 函数返回协程的情况
                if asyncio.iscoroutine(result):
                    return _run_coro_audit(result, start, session_id, user_id, store_id, tool_name, args, kwargs)
                duration_ms = int((time.monotonic() - start) * 1000)
                _audit_sync(
                    session_id, user_id, store_id,
                    f"tool:{tool_name}",
                    {"args": str(args), "kwargs": str(kwargs), "result": "success"},
                    duration_ms,
                )
                return result
            except Exception as e:
                duration_ms = int((time.monotonic() - start) * 1000)
                _audit_sync(
                    session_id, user_id, store_id,
                    f"tool:{tool_name}:error",
                    {"args": str(args), "kwargs": str(kwargs), "error": str(e)},
                    duration_ms,
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def _get_state_field(state, field: str, default: str = "unknown") -> str:
    """从 state 中安全提取字段"""
    if state and isinstance(state, dict):
        return state.get(field, default)
    if state and hasattr(state, field):
        return getattr(state, field, default)
    return default


async def _run_coro_audit(coro, start, session_id, user_id, store_id, tool_name, args, kwargs):
    """运行协程并记录审计"""
    try:
        result = await coro
        duration_ms = int((time.monotonic() - start) * 1000)
        _audit_async(
            session_id, user_id, store_id,
            f"tool:{tool_name}",
            {"args": str(args), "kwargs": str(kwargs), "result": "success"},
            duration_ms,
        )
        return result
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        _audit_async(
            session_id, user_id, store_id,
            f"tool:{tool_name}:error",
            {"args": str(args), "kwargs": str(kwargs), "error": str(e)},
            duration_ms,
        )
        raise


def _audit_async(session_id, user_id, store_id, action, payload, duration_ms):
    """异步记录审计（不阻塞）"""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(write_audit_log(session_id, user_id, store_id, action, payload, duration_ms))
    except RuntimeError:
        # 无 running loop，创建新 task
        asyncio.create_task(write_audit_log(session_id, user_id, store_id, action, payload, duration_ms))


def _audit_sync(session_id, user_id, store_id, action, payload, duration_ms):
    """同步记录审计"""
    try:
        asyncio.run(write_audit_log(session_id, user_id, store_id, action, payload, duration_ms))
    except RuntimeError:
        # 已经在 event loop 中，用 call_soon
        import threading
        t = threading.Thread(target=lambda: asyncio.run(
            write_audit_log(session_id, user_id, store_id, action, payload, duration_ms)
        ))
        t.start()
        t.join(timeout=1)

