# ============================================================
# ERP MCP Server — Phase 6.1
# 功能：商品主数据查询（名称/条码/分类/进价/供应商）
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
server = Server("erp-mcp")


# ============================================================
# Tools（ERP 集成）
# ============================================================
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="erp_get_product",
            description="查询ERP商品主数据（名称/条码/分类/进价/供应商）",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "商品ID（ERP系统内编码）",
                        "examples": ["P00001"],
                    },
                },
                "required": ["product_id"],
            },
        ),
        Tool(
            name="erp_search_products",
            description="按名称/条码/分类搜索ERP商品列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "category": {"type": "string", "description": "商品分类"},
                    "limit": {"type": "integer", "default": 20, "description": "最多返回条数"},
                },
            },
        ),
        Tool(
            name="erp_get_supplier",
            description="查询供应商信息（名称/联系人/账期）",
            inputSchema={
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "string", "description": "供应商ID"},
                },
                "required": ["supplier_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "erp_get_product":
        result = await _get_product(arguments["product_id"])
    elif name == "erp_search_products":
        result = await _search_products(
            arguments.get("query", ""),
            arguments.get("category", ""),
            arguments.get("limit", 20),
        )
    elif name == "erp_get_supplier":
        result = await _get_supplier(arguments["supplier_id"])
    else:
        result = {"error": f"Unknown tool: {name}"}
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


# ============================================================
# ERP API 实现（Mock，生产环境替换为真实 API 调用）
# ============================================================
import os

ERP_API_URL = os.environ.get("ERP_API_URL", "https://erp.example.com/api/v1")
ERP_API_KEY = os.environ.get("ERP_API_KEY", "")


async def _get_product(product_id: str) -> dict:
    """
    查询商品主数据
    生产实现：GET {ERP_API_URL}/products/{product_id}
    """
    # Mock 数据，生产环境替换为真实 API
    mock_products = {
        "P00001": {
            "product_id": "P00001",
            "barcode": "6926156000012",
            "name": "伊利纯牛奶250ml",
            "category": "乳制品",
            "brand": "伊利",
            "unit": "箱",
            "specification": "250ml*12",
            "cost_price": 45.60,
            "retail_price": 59.00,
            "supplier_id": "S0001",
            "supplier_name": "伊利集团华东分公司",
            "min_order_quantity": 10,
            "shelf_life_days": 180,
        },
        "P00002": {
            "product_id": "P00002",
            "barcode": "6926156000029",
            "name": "农夫山泉550ml",
            "category": "饮料",
            "brand": "农夫山泉",
            "unit": "箱",
            "specification": "550ml*24",
            "cost_price": 14.80,
            "retail_price": 24.00,
            "supplier_id": "S0002",
            "supplier_name": "农夫山泉股份有限公司",
            "min_order_quantity": 50,
            "shelf_life_days": 365,
        },
    }
    if product_id in mock_products:
        return mock_products[product_id]
    return {"product_id": product_id, "error": "商品不存在"}


async def _search_products(query: str, category: str, limit: int) -> dict:
    """搜索商品列表"""
    all_products = [
        {"product_id": "P00001", "name": "伊利纯牛奶250ml", "barcode": "6926156000012", "category": "乳制品"},
        {"product_id": "P00002", "name": "农夫山泉550ml", "barcode": "6926156000029", "category": "饮料"},
        {"product_id": "P00003", "name": "蒙牛酸酸乳", "barcode": "6926156000036", "category": "乳制品"},
        {"product_id": "P00004", "name": "康师傅方便面", "barcode": "6926156000043", "category": "食品"},
        {"product_id": "P00005", "name": "茅台王子酒", "barcode": "6926156000050", "category": "酒类"},
    ]
    results = [
        p for p in all_products
        if query.lower() in p["name"].lower()
        or query.lower() in p.get("barcode", "").lower()
        or (category and p["category"] == category)
    ]
    return {"total": len(results), "products": results[:limit]}


async def _get_supplier(supplier_id: str) -> dict:
    """查询供应商信息"""
    mock_suppliers = {
        "S0001": {
            "supplier_id": "S0001",
            "name": "伊利集团华东分公司",
            "contact": "张经理",
            "phone": "021-xxxx-xxxx",
            "payment_days": 30,
            "rating": "A",
        },
        "S0002": {
            "supplier_id": "S0002",
            "name": "农夫山泉股份有限公司",
            "contact": "李经理",
            "phone": "0571-xxxx-xxxx",
            "payment_days": 45,
            "rating": "A+",
        },
    }
    if supplier_id in mock_suppliers:
        return mock_suppliers[supplier_id]
    return {"supplier_id": supplier_id, "error": "供应商不存在"}


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
