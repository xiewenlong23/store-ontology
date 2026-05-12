# ============================================================
# MCP 工具接入 — Phase 6.4
# 通过 langchain-mcp-adapters 将外部 MCP Server 作为 LangChain Tool 接入
# 验证 API（v0.2.2）：
#   MultiServerMCPClient(connections={server: {command/transport/url}})
#   load_mcp_tools(session, connection=conn, tool_name_prefix=True)
# ============================================================
import os
import asyncio
from typing import Any

import yaml

from langchain_mcp_adapters.client import MultiServerMCPClient, StdioConnection
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import BaseTool

from app.audit.logger import get_logger

log = get_logger("mcp_tools")

# ============================================================
# 全局状态
# ============================================================
_mcp_client: MultiServerMCPClient | None = None
_mcp_tools: list[BaseTool] = []


# ============================================================
# 初始化（app 启动时调用）
# ============================================================
async def init_mcp_clients() -> list[BaseTool]:
    """
    从 config/mcp.yaml 读取配置，初始化所有 MCP Server 连接，
    通过 langchain-mcp-adapters 加载工具列表。

    启动时机：app/main.py lifespan
    关闭时机：app/main.py shutdown → close_mcp_clients()
    """
    global _mcp_client, _mcp_tools

    config_path = os.path.join(os.path.dirname(__file__), "../../../config/mcp.yaml")
    if not os.path.exists(config_path):
        log.warning("mcp.yaml not found, skipping MCP initialization")
        return []

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    mcp_servers: dict[str, dict] = config.get("mcp_servers", {})
    if not mcp_servers:
        return []

    # 构建 MultiServerMCPClient 连接配置
    connections: dict[str, dict] = {}
    for server_name, server_config in mcp_servers.items():
        if not server_config.get("enabled", False):
            continue

        transport = server_config.get("transport", "stdio")
        env = server_config.get("env", {})

        # 替换 ${ENV_VAR} 占位符
        resolved_env: dict[str, str] = {}
        for k, v in env.items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                resolved_env[k] = os.environ.get(v[2:-1], "")
            else:
                resolved_env[k] = v

        if transport == "stdio":
            command = server_config.get("command", [])
            if not command:
                log.warning(f"MCP server '{server_name}': no command configured, skipping")
                continue
            connections[server_name] = {
                "command": command[0],
                "args": command[1:],
                "transport": "stdio",
                "env": resolved_env,
            }
        elif transport == "sse":
            url = server_config.get("url", "")
            connections[server_name] = {"url": url, "transport": "sse", "env": resolved_env}
        else:
            log.warning(f"MCP server '{server_name}': unsupported transport '{transport}', skipping")
            continue

    if not connections:
        log.info("No MCP servers enabled, skipping initialization")
        return []

    # 初始化 MultiServerMCPClient
    try:
        _mcp_client = MultiServerMCPClient(connections=connections)
    except Exception as e:
        log.error("Failed to initialize MultiServerMCPClient", error=str(e))
        return []

    # 加载工具
    try:
        tools = await _mcp_client.get_tools()
        _mcp_tools = [_wrap_mcp_tool(t, server_name) for server_name, t in tools]
        log.info(f"MCP tools loaded", count=len(_mcp_tools), tools=[t.name for t in _mcp_tools])
    except Exception as e:
        log.error("Failed to load MCP tools", error=str(e))
        await close_mcp_clients()
        return []

    return _mcp_tools


async def close_mcp_clients():
    """关闭 MCP Client（在 app shutdown 时调用）"""
    global _mcp_client, _mcp_tools
    if _mcp_client:
        try:
            await _mcp_client.close()
        except Exception as e:
            log.error("Error closing MCP client", error=str(e))
        _mcp_client = None
        _mcp_tools = []


def get_mcp_tools() -> list[BaseTool]:
    """获取所有已加载的 MCP 工具"""
    return _mcp_tools


# ============================================================
# 工具审计包装
# ============================================================
def _wrap_mcp_tool(tool: BaseTool, server_name: str) -> BaseTool:
    """
    将 MCP 工具包装为带审计日志的版本。
    保留原工具的所有元数据，只替换 invoke 方法。
    """
    original_invoke = tool.invoke

    async def audited_invoke(config: dict) -> Any:
        state = config.get("state", {})
        session_id = _safe_get(state, "session_id", "unknown")
        user_id = _safe_get(state, "user_id", "unknown")
        store_id = _safe_get(state, "store_id", "unknown")
        start = _now_ms()
        try:
            result = await original_invoke(config)
            _log_mcp_call(session_id, user_id, store_id, server_name, tool.name, start, True, None)
            return result
        except Exception as e:
            _log_mcp_call(session_id, user_id, store_id, server_name, tool.name, start, False, str(e))
            raise

    tool.invoke = audited_invoke
    return tool


def _safe_get(d: dict, key: str, default: str) -> str:
    return d.get(key, default) if isinstance(d, dict) else default


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


def _log_mcp_call(session_id, user_id, store_id, server_name, tool_name, start_ms, success, error):
    from app.audit.audit_service import write_audit_log
    duration_ms = _now_ms() - start_ms
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            write_audit_log(
                session_id=session_id,
                user_id=user_id,
                store_id=store_id,
                action=f"mcp:{server_name}:{tool_name}" + (":error" if not success else ""),
                payload={"server": server_name, "tool": tool_name, "success": success, "error": error},
                duration_ms=duration_ms,
            )
        )
    except RuntimeError:
        asyncio.create_task(
            write_audit_log(
                session_id=session_id,
                user_id=user_id,
                store_id=store_id,
                action=f"mcp:{server_name}:{tool_name}" + (":error" if not success else ""),
                payload={"server": server_name, "tool": tool_name, "success": success, "error": error},
                duration_ms=duration_ms,
            )
        )
