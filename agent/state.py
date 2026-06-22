"""请求级共享状态（contextvars）。

P5：从 main.py 拆出，让 routers 无需循环 import main 即可访问
tenant_ctx / auth_ctx。main.py 和各 router 都从此处 import。

- tenant_ctx：由 tenant_middleware 注入，工具层经 _tc_ctx() 读取。
- auth_ctx：由 auth_middleware 注入，工具层经 _get_actor() 派生可信身份。
"""
import contextvars

from engine.tenant import TenantContext
from engine.auth import AuthContext

# 当前请求的租户上下文（workspace_name + org_unit_id）。
tenant_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "tenant_ctx", default=TenantContext.default())

# 当前请求的可信身份。auth_middleware 注入；WP6 强制模式下无 token → 401。
auth_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "auth_ctx", default=AuthContext.anonymous())
