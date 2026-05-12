"""
tests/unit/test_mcp_tools.py — Phase 7.1
MCP 工具单元测试（Mock langchain-mcp-adapters）
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.tools import BaseTool


class MockMcpTool(BaseTool):
    """Mock MCP BaseTool 实例"""
    name = "erp_get_product"
    description = "查询ERP商品主数据"
    args_schema = MagicMock()

    @classmethod
    def from_conversation(cls, **kwargs):
        return cls()

    def invoke(self, config):
        return '{"product_id": "P00001", "name": "伊利纯牛奶250ml"}'


@pytest.mark.asyncio
async def test_mcp_tool_audit_wrapper_success():
    """MCP 工具调用：成功时写入审计日志"""
    from app.agent.tools.mcp_tools import _wrap_mcp_tool

    tool = _wrap_mcp_tool(MockMcpTool(), "erp")

    with patch("app.agent.tools.mcp_tools.write_audit_log") as mock_audit:
        mock_audit.return_value = AsyncMock()
        config = {"state": {"session_id": "sess-1", "user_id": "u001", "store_id": "STORE_001"}}
        result = await tool.invoke(config)

    mock_audit.assert_called_once()
    call_args = mock_audit.call_args
    assert call_args.kwargs["session_id"] == "sess-1"
    assert call_args.kwargs["action"] == "mcp:erp:erp_get_product"


@pytest.mark.asyncio
async def test_mcp_tool_audit_wrapper_error():
    """MCP 工具调用：失败时记录 error action"""
    from app.agent.tools.mcp_tools import _wrap_mcp_tool

    class FailingTool(MockMcpTool):
        def invoke(self, config):
            raise RuntimeError("Connection refused")

    tool = _wrap_mcp_tool(FailingTool(), "wms")

    with patch("app.agent.tools.mcp_tools.write_audit_log") as mock_audit:
        mock_audit.return_value = AsyncMock()
        config = {"state": {"session_id": "sess-2", "user_id": "u002", "store_id": "STORE_002"}}

        with pytest.raises(RuntimeError):
            await tool.invoke(config)

    call_args = mock_audit.call_args
    assert call_args.kwargs["action"] == "mcp:wms:erp_get_product:error"
    assert "Connection refused" in call_args.kwargs["payload"]["error"]


def test_get_mcp_tools_returns_empty_before_init():
    """MCP 工具未初始化时返回空列表"""
    from app.agent.tools.mcp_tools import get_mcp_tools
    # 全局变量初始为空
    assert get_mcp_tools() == []
