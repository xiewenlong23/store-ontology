#!/usr/bin/env python3
"""
ToolContext — 工具执行上下文

为扩展预留的设计：
- 当前：单店单场景，store_id 默认值 "STORE-001"
- 后续：多门店时，从认证信息注入真实的 tenant_id

使用方式：
- 工具函数通过 context.get() 获取当前上下文
- router 层通过 ContextManager 设置上下文
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from contextvars import ContextVar
import json
from pathlib import Path


# ── 权限配置加载 ────────────────────────────────────────────

def _load_permissions() -> dict:
    path = Path(__file__).parent.parent.parent / "data" / "permissions.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"roles": {}}


_PERMISSIONS = _load_permissions()


def _role_permissions(role: str) -> list[str]:
    return _PERMISSIONS.get("roles", {}).get(role, {}).get("permissions", [])


# ── 上下文变量 ──────────────────────────────────────────────

# 全局上下文变量（thread-safe）
_current_context: ContextVar["ToolContext"] = ContextVar("current_context", default=None)


@dataclass
class ToolContext:
    """
    工具执行上下文。

    包含：
    - tenant_id: 租户/门店 ID（多门店扩展点）
    - user_id: 用户 ID（权限扩展点）
    - user_role: 用户角色
    - 请求级业务数据: product_id, category 等

    扩展预留字段：
    - permissions: 权限列表
    - metadata: 任意元数据
    """
    # 租户/门店（多门店扩展点）
    store_id: str = "STORE-001"

    # 用户信息（权限扩展点）
    user_id: Optional[str] = None
    user_role: Optional[str] = None  # manager / clerk / headquarters / ...

    # 请求级业务数据
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    expiry_date: Optional[str] = None
    stock: Optional[int] = None

    # 扩展预留
    permissions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        """检查是否拥有某权限（基于 role-permission 矩阵）"""
        perms = _role_permissions(self.user_role or "clerk")
        return permission in perms

    def is_manager(self) -> bool:
        """是否是店长"""
        return self.user_role == "manager"

    def is_clerk(self) -> bool:
        """是否是店员"""
        return self.user_role == "clerk"

    def is_headquarters(self) -> bool:
        """是否是总部人员"""
        return self.user_role == "headquarters"


class ContextManager:
    """
    上下文管理器。

    使用方式：
        ctx = ToolContext(store_id="STORE-001", user_id="user_001")
        with ContextManager(ctx):
            # 此处调用的工具函数可以通过 context.get() 获取上下文
            result = some_tool_function()
    """

    def __init__(self, context: ToolContext):
        self._token = None
        self._context = context

    def __enter__(self) -> ToolContext:
        self._token = _current_context.set(self._context)
        return self._context

    def __exit__(self, exc_type, exc_val, exc_tb):
        _current_context.reset(self._token)
        return False


def get_context() -> ToolContext:
    """
    获取当前工具上下文。

    Returns:
        ToolContext: 当前上下文，如果未设置则返回默认单店上下文

    Note:
        在工具函数内部调用此方法获取上下文信息
    """
    ctx = _current_context.get()
    if ctx is None:
        # 兼容：未设置上下文时返回默认单店上下文
        return ToolContext()
    return ctx


# 别名：用于 middleware 兼容
get_current_context = get_context


def require_context() -> ToolContext:
    """
    获取当前工具上下文（必须已设置）。

    Raises:
        RuntimeError: 如果上下文未设置

    Note:
        用于必须在有上下文时才能执行的工具
    """
    ctx = _current_context.get()
    if ctx is None:
        raise RuntimeError("ToolContext not set. Use ContextManager to set context before calling tools.")
    return ctx
