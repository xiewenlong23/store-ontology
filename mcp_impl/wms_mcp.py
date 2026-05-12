# ============================================================
# WMS MCP Server — Phase 6.2
# 功能：库存查询（实时库存/在途量/批次信息）
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
server = Server("wms-mcp")


# ============================================================
# Tools（WMS 集成）
# ============================================================
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="wms_get_inventory",
            description="查询商品实时库存（当前库存量/库位/批次）",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "商品ID"},
                    "store_id": {"type": "string", "description": "门店ID"},
                },
                "required": ["product_id", "store_id"],
            },
        ),
        Tool(
            name="wms_check_stock",
            description="检查某商品在某门店是否有货",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "商品ID"},
                    "store_id": {"type": "string", "description": "门店ID"},
                    "required_quantity": {"type": "number", "description": "需求数量"},
                },
                "required": ["product_id", "store_id", "required_quantity"],
            },
        ),
        Tool(
            name="wms_get_inventory_alerts",
            description="查询库存预警（低于安全库存/临期）",
            inputSchema={
                "type": "object",
                "properties": {
                    "store_id": {"type": "string", "description": "门店ID"},
                    "alert_type": {"type": "string", "enum": ["low_stock", "expiring", "all"], "default": "all"},
                },
                "required": ["store_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "wms_get_inventory":
        result = await _get_inventory(arguments["product_id"], arguments["store_id"])
    elif name == "wms_check_stock":
        result = await _check_stock(
            arguments["product_id"],
            arguments["store_id"],
            arguments["required_quantity"],
        )
    elif name == "wms_get_inventory_alerts":
        result = await _get_alerts(arguments["store_id"], arguments.get("alert_type", "all"))
    else:
        result = {"error": f"Unknown tool: {name}"}
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


# ============================================================
# WMS API 实现（Mock，生产环境替换为真实 API 调用）
# ============================================================
import os

WMS_API_URL = os.environ.get("WMS_API_URL", "https://wms.example.com/api/v1")
WMS_API_KEY = os.environ.get("WMS_API_KEY", "")

# Mock 库存数据
_MOCK_INVENTORY = {
    ("P00001", "STORE_001"): {
        "product_id": "P00001",
        "store_id": "STORE_001",
        "current_stock": 50,
        "available_stock": 45,
        "reserved_stock": 5,
        "in_transit_stock": 20,
        "safety_stock": 10,
        "location": "A区-01-03",
        "batch_no": "B20260501",
        "shelf_date": "2025-11-01",
        "last_restock_date": "2025-05-01",
    },
    ("P00002", "STORE_001"): {
        "product_id": "P00002",
        "store_id": "STORE_001",
        "current_stock": 200,
        "available_stock": 200,
        "reserved_stock": 0,
        "in_transit_stock": 100,
        "safety_stock": 30,
        "location": "B区-02-05",
        "batch_no": "B20260508",
        "shelf_date": "2026-05-08",
        "last_restock_date": "2025-05-08",
    },
    ("P00003", "STORE_001"): {
        "product_id": "P00003",
        "store_id": "STORE_001",
        "current_stock": 5,
        "available_stock": 5,
        "reserved_stock": 0,
        "in_transit_stock": 0,
        "safety_stock": 15,
        "location": "A区-01-01",
        "batch_no": "B20260420",
        "shelf_date": "2025-10-20",
        "last_restock_date": "2025-04-20",
    },
}


async def _get_inventory(product_id: str, store_id: str) -> dict:
    """查询实时库存"""
    key = (product_id, store_id)
    if key in _MOCK_INVENTORY:
        return _MOCK_INVENTORY[key]
    return {
        "product_id": product_id,
        "store_id": store_id,
        "current_stock": 0,
        "available_stock": 0,
        "in_transit_stock": 0,
        "safety_stock": 0,
        "status": "无库存记录",
    }


async def _check_stock(product_id: str, store_id: str, required_quantity: float) -> dict:
    """检查库存是否足够"""
    inv = await _get_inventory(product_id, store_id)
    available = inv.get("available_stock", 0)
    sufficient = available >= required_quantity
    return {
        "product_id": product_id,
        "store_id": store_id,
        "required": required_quantity,
        "available": available,
        "sufficient": sufficient,
        "shortage": max(0, required_quantity - available),
        "in_transit": inv.get("in_transit_stock", 0),
    }


async def _get_alerts(store_id: str, alert_type: str) -> dict:
    """查询库存预警"""
    alerts = []
    for (pid, sid), inv in _MOCK_INVENTORY.items():
        if sid != store_id:
            continue
        # 低库存预警
        if inv["current_stock"] <= inv["safety_stock"]:
            alerts.append({
                "type": "low_stock",
                "product_id": pid,
                "current_stock": inv["current_stock"],
                "safety_stock": inv["safety_stock"],
                "shortage": inv["safety_stock"] - inv["current_stock"],
            })
        # 临期预警（已在 ABOX 的 SPARQL 里覆盖，此处从 WMS 补充）
        if "shelf_date" in inv:
            from datetime import date, timedelta
            shelf_date = date.fromisoformat(inv["shelf_date"])
            if (shelf_date - date.today()).days <= 7:
                alerts.append({
                    "type": "expiring",
                    "product_id": pid,
                    "shelf_date": inv["shelf_date"],
                    "days_until_expiry": (shelf_date - date.today()).days,
                })

    if alert_type != "all":
        alerts = [a for a in alerts if a["type"] == alert_type]
    return {"store_id": store_id, "alert_type": alert_type, "alerts": alerts, "total": len(alerts)}


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
