# ============================================================
# MCP 工具测试 — 按实际 mcp_tools.py 实现重写
# mock 掉 MultiServerMCPClient，避免真实连接
# ============================================================
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class MockBaseTool:
    """模拟 LangChain BaseTool"""
    name = "test_tool"
    description = "test tool"

    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.invoke = AsyncMock(return_value={"result": "ok"})


class TestMcpToolsInit:
    """测试 MCP 工具加载（mock MultiServerMCPClient）"""

    @pytest.mark.asyncio
    async def test_init_mcp_clients_no_config(self):
        """mcp.yaml 不存在时不报错，返回空列表"""
        with patch("os.path.exists", return_value=False):
            from app.agent.tools.mcp_tools import init_mcp_clients
            tools = await init_mcp_clients()
            assert tools == []

    @pytest.mark.asyncio
    async def test_init_mcp_clients_no_servers_enabled(self):
        """mcp.yaml 存在但无 enabled 服务器时返回空列表"""
        mock_config = {"mcp_servers": {}}

        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("yaml.safe_load", return_value=mock_config):
                    from app.agent.tools.mcp_tools import init_mcp_clients
                    tools = await init_mcp_clients()
                    assert tools == []


class TestMcpToolsGetTools:
    """测试 get_mcp_tools 全局状态"""

    def test_get_mcp_tools_empty_before_init(self):
        """初始化前返回空列表"""
        # 重置全局状态
        import app.agent.tools.mcp_tools as mcp_module
        mcp_module._mcp_tools = []
        mcp_module._mcp_client = None

        from app.agent.tools.mcp_tools import get_mcp_tools
        assert get_mcp_tools() == []


class TestWrapMcpTool:
    """测试 MCP 工具审计包装器"""

    @pytest.mark.asyncio
    async def test_wrap_mcp_tool_success(self):
        """工具调用成功时记录审计日志（mock audit）"""
        from app.agent.tools.mcp_tools import _wrap_mcp_tool

        mock_tool = MagicMock()
        mock_tool.name = "erp_get_product"
        mock_invoke = AsyncMock(return_value={"product_id": "P001"})
        mock_tool.invoke = mock_invoke

        wrapped = _wrap_mcp_tool(mock_tool, "erp_server")

        # 调用包装后的工具
        config = {"state": {"session_id": "sess1", "user_id": "u1", "store_id": "STORE_001"}}
        result = await wrapped.invoke(config)

        assert result == {"product_id": "P001"}
        # 包装后原 invoke 被调用一次
        mock_invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_wrap_mcp_tool_error(self):
        """工具调用失败时抛出异常"""
        from app.agent.tools.mcp_tools import _wrap_mcp_tool

        mock_tool = MagicMock()
        mock_tool.name = "erp_get_product"
        mock_tool.invoke = AsyncMock(side_effect=Exception("ERP Error"))

        wrapped = _wrap_mcp_tool(mock_tool, "erp_server")

        config = {"state": {"session_id": "sess1", "user_id": "u1", "store_id": "STORE_001"}}

        with pytest.raises(Exception, match="ERP Error"):
            await wrapped.invoke(config)


class TestCloseMcpClients:
    """测试 MCP Client 关闭"""

    @pytest.mark.asyncio
    async def test_close_mcp_clients_no_client(self):
        """无 client 时安全关闭"""
        import app.agent.tools.mcp_tools as mcp_module
        mcp_module._mcp_client = None
        mcp_module._mcp_tools = []

        from app.agent.tools.mcp_tools import close_mcp_clients
        await close_mcp_clients()

        assert mcp_module._mcp_client is None
        assert mcp_module._mcp_tools == []
