# ============================================================
# 链路追踪工具 — Phase 5.3
# @traced_tool 装饰器 + span 上下文管理
# ============================================================
import time
import functools
import asyncio
from typing import Any, Callable, Optional
from app.observability.langsmith import langsmith_tracing_enabled
from app.audit.logger import get_logger

log = get_logger("tracing")

# 延迟加载 LangChain tracer
_tracer = None


def _get_tracer():
    """延迟加载 LangChain tracer"""
    global _tracer
    if _tracer is not None:
        return _tracer
    if not langsmith_tracing_enabled():
        return None
    try:
        from langchain_core.tracers.langchain import LangChainTracer
        _tracer = LangChainTracer()
        return _tracer
    except ImportError:
        return None


def traced_tool(
    name: str = None,
    tags: list[str] = None,
):
    """
    工具级链路追踪装饰器
    用法：@traced_tool("query_expiring_products", tags=["sparql", "graphdb"])

    自动记录：
    - 工具名称
    - 输入参数（脱敏后）
    - 执行时长
    - 成功/失败
    - LangSmith span
    """
    tool_name = name or "unknown"

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _run_and_trace(func, args, kwargs, tool_name, tags, is_async=True)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                # sync 函数内部返回协程 → 用 await
                return _run_and_trace_async_coro(result, args, kwargs, func, tool_name, tags)
            _end_span(tool_name, tags, 0, success=True)
            return result

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


async def _run_and_trace(func, args, kwargs, name, tags, is_async: bool):
    """async 函数的追踪"""
    tracer = _get_tracer()
    span_start = time.monotonic()
    error = None
    try:
        result = await func(*args, **kwargs)
        _end_span(name, tags, int((time.monotonic() - span_start) * 1000), success=True)
        return result
    except Exception as e:
        error = e
        _end_span(name, tags, int((time.monotonic() - span_start) * 1000), success=False, error=str(e))
        raise


async def _run_and_trace_async_coro(coro, args, kwargs, func, name, tags):
    """sync wrapper 里 await 协程的追踪"""
    tracer = _get_tracer()
    span_start = time.monotonic()
    try:
        result = await coro
        _end_span(name, tags, int((time.monotonic() - span_start) * 1000), success=True)
        return result
    except Exception as e:
        _end_span(name, tags, int((time.monotonic() - span_start) * 1000), success=False, error=str(e))
        raise


def _end_span(name: str, tags, duration_ms: int, success: bool, error: str = None):
    """记录 span 并写 structlog"""
    log.debug(
        "tool_trace",
        tool=name,
        duration_ms=duration_ms,
        success=success,
        error=error,
        tags=tags or [],
    )

    tracer = _get_tracer()
    if tracer and hasattr(tracer, "end_span"):
        try:
            attrs = {"tool": name, "duration_ms": duration_ms, "success": success}
            if error:
                attrs["error"] = error
            if tags:
                attrs["tags"] = tags
            tracer.end_span(**attrs)
        except Exception:
            pass
