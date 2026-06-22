"""routers 共享 helper（P5：从 main.py 拆出，避免 router 循环 import main）。

- resolve_workspace_name：解析当前请求的 workspace 标识。
  优先级：X-Workspace header > URL {cid} 参数 > 默认 jjy。
"""
from typing import Optional


def resolve_workspace_name(request, url_cid: Optional[str] = None) -> str:
    """统一解析当前请求的 workspace 标识（架构 spec §3.4）。

    URL {cid} 回退保证旧前端调用（admin/dashboard 路由）仍可用。
    """
    ws = getattr(request.state, "workspace_name", None)
    if ws:
        return ws
    if url_cid:
        return url_cid
    return "jjy"
