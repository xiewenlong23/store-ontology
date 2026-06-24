"""FastAPI 路由模块集合（P5：从 main.py 拆出）。

各模块暴露 ``router``（APIRouter），main.py 用 ``app.include_router(...)`` 注册。
共享状态（contextvars）在 ``agent.state``；共享 helper 在 ``agent.routers._shared``。
"""
from agent.routers.auth import router as auth_router
from agent.routers.admin import router as admin_router
from agent.routers.dashboard import router as dashboard_router
from agent.routers.webhooks import router as webhooks_router
from agent.routers.action_logs import router as action_logs_router

__all__ = ["auth_router", "admin_router", "dashboard_router",
           "webhooks_router", "action_logs_router"]
