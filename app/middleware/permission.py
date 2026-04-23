from functools import wraps
from fastapi import HTTPException

from app.services.context import get_context


def require_role(*allowed_roles: str):
    """
    FastAPI route decorator — enforce user_role field.

    Usage:
        @router.patch("/{task_id}/confirm")
        @require_role("manager", "headquarters")
        def confirm_task(...): ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = get_current_context()
            if ctx.user_role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"此操作需要角色 {allowed_roles}，当前角色: {ctx.user_role or '未认证'}"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(*required_permissions: str):
    """
    FastAPI route decorator — enforce specific permission string.

    Usage:
        @router.post("/some-action")
        @require_permission("task:confirm", "task:execute")
        def some_action(...): ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = get_current_context()
            for perm in required_permissions:
                if not ctx.has_permission(perm):
                    raise HTTPException(
                        status_code=403,
                        detail=f"权限不足，需要: {perm}"
                    )
            return await func(*args, **kwargs)
        return wrapper
    return decorator