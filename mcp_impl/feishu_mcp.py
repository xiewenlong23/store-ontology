# ============================================================
# 飞书 MCP Server — Phase 6.3
# 功能：发送审批卡片/消息推送
# 协议：MCP（Model Context Protocol），通过 STDIO 通信
# ============================================================
import sys
import json
from typing import Any
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# ============================================================
# Server Setup
# ============================================================
server = Server("feishu-mcp")


# ============================================================
# Tools（飞书通知）
# ============================================================
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="feishu_send_approval_card",
            description="发送审批卡片消息到飞书（支持approve/edit/reject三个按钮）",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "飞书会话ID"},
                    "card_content": {"type": "object", "description": "卡片内容（见 hitl_notifier）"},
                },
                "required": ["chat_id", "card_content"],
            },
        ),
        Tool(
            name="feishu_send_text",
            description="发送纯文本消息到飞书",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "飞书会话ID"},
                    "content": {"type": "string", "description": "文本内容"},
                },
                "required": ["chat_id", "content"],
            },
        ),
        Tool(
            name="feishu_get_user_info",
            description="查询飞书用户信息（ID/名称/部门）",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "飞书用户ID（user_id）"},
                },
                "required": ["user_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "feishu_send_approval_card":
        result = await _send_approval_card(arguments["chat_id"], arguments["card_content"])
    elif name == "feishu_send_text":
        result = await _send_text(arguments["chat_id"], arguments["content"])
    elif name == "feishu_get_user_info":
        result = await _get_user_info(arguments["user_id"])
    else:
        result = {"error": f"Unknown tool: {name}"}
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


# ============================================================
# 飞书 API 实现（Mock，生产环境替换为真实 API 调用）
# ============================================================
import os

FEISHU_BOT_TOKEN = os.environ.get("FEISHU_BOT_TOKEN", "")
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")


async def _send_approval_card(chat_id: str, card_content: dict) -> dict:
    """
    发送审批卡片
    生产实现：POST https://open.feishu.cn/open-apis/im/v1/messages
    """
    # Mock 返回
    return {
        "status": "success",
        "chat_id": chat_id,
        "message_id": f"mock_msg_{chat_id}_{id(card_content)}",
        "card_type": "approval",
    }


async def _send_text(chat_id: str, content: str) -> dict:
    """发送纯文本消息"""
    return {
        "status": "success",
        "chat_id": chat_id,
        "message_id": f"mock_msg_{chat_id}_{hash(content)}",
        "content": content,
    }


async def _get_user_info(user_id: str) -> dict:
    """查询用户信息"""
    mock_users = {
        "u001": {"user_id": "u001", "name": "张店长", "department": "威海经开区店", "role": "store_manager"},
        "u002": {"user_id": "u002", "name": "李店员", "department": "威海经开区店", "role": "clerk"},
        "u003": {"user_id": "u003", "name": "王总部", "department": "总部商品部", "role": "headquarters"},
    }
    if user_id in mock_users:
        return mock_users[user_id]
    return {"user_id": user_id, "error": "用户不存在"}


# ============================================================
# STDIO Server Entry Point
# ============================================================
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
