#!/usr/bin/env python
"""MCP Server wrapping Ozon Seller API — allows Claude to call Ozon directly.

Tools exposed:
  - ozon_category_tree         → POST /v1/description-category/tree
  - ozon_category_attributes   → POST /v1/description-category/attribute
  - ozon_category_values       → POST /v1/description-category/attribute/values
  - ozon_product_import        → POST /v3/product/import
  - ozon_product_info          → POST /v3/product/info/list
  - ozon_product_list          → POST /v3/product/list
  - ozon_product_import_info   → POST /v1/product/import/info
"""

import json
import os
import sys
from pathlib import Path

import anyio
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Load .env ───────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

CLIENT_ID = os.getenv("OZON_CLIENT_ID", "")
API_KEY = os.getenv("OZON_API_KEY", "")
BASE_URL = os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru").rstrip("/")

# ── Shared httpx client ─────────────────────────────────────────
_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "Client-Id": CLIENT_ID,
                "Api-Key": API_KEY,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(60.0),
        )
    return _client


async def ozon_post(path: str, body: dict | None = None) -> dict:
    """POST to Ozon API, return JSON response."""
    client = await get_client()
    resp = await client.post(path, json=body)
    return {"status": resp.status_code, "body": resp.json() if resp.text else {}}


# ── MCP Server ──────────────────────────────────────────────────
server = Server("ozon-seller-api")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ozon_category_tree",
            description="获取 Ozon 完整类目树（含 type_id）。POST /v1/description-category/tree",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "语言: DEFAULT / RU / EN / ZH",
                        "default": "DEFAULT",
                    }
                },
            },
        ),
        Tool(
            name="ozon_category_attributes",
            description="获取指定类目的特征/属性列表。POST /v1/description-category/attribute",
            inputSchema={
                "type": "object",
                "properties": {
                    "description_category_id": {
                        "type": "integer",
                        "description": "类目 ID",
                    },
                    "type_id": {
                        "type": "integer",
                        "description": "商品类型 ID（从 category_tree 获取）",
                        "default": 0,
                    },
                    "language": {
                        "type": "string",
                        "description": "语言",
                        "default": "DEFAULT",
                    },
                },
                "required": ["description_category_id"],
            },
        ),
        Tool(
            name="ozon_category_values",
            description="获取特征/属性的字典值列表。POST /v1/description-category/attribute/values",
            inputSchema={
                "type": "object",
                "properties": {
                    "attribute_id": {
                        "type": "integer",
                        "description": "属性 ID",
                    },
                    "description_category_id": {
                        "type": "integer",
                        "description": "类目 ID",
                    },
                    "type_id": {
                        "type": "integer",
                        "description": "商品类型 ID",
                        "default": 0,
                    },
                    "language": {
                        "type": "string",
                        "description": "语言",
                        "default": "DEFAULT",
                    },
                    "last_value_id": {
                        "type": "integer",
                        "description": "分页起始值",
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "每页数量",
                        "default": 5000,
                    },
                },
                "required": ["attribute_id", "description_category_id"],
            },
        ),
        Tool(
            name="ozon_product_import",
            description="创建/更新商品到 Ozon。POST /v3/product/import。传入完整的 items 数组。",
            inputSchema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "商品列表，每个元素为 v3 格式的 V3ImportProductsRequestItem",
                        "items": {"type": "object"},
                    }
                },
                "required": ["items"],
            },
        ),
        Tool(
            name="ozon_product_info",
            description="根据 product_id 或 offer_id 获取商品信息。POST /v3/product/info/list",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Ozon product IDs (最多100)",
                    },
                    "offer_id": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Offer IDs (最多100)",
                    },
                },
            },
        ),
        Tool(
            name="ozon_product_list",
            description="翻页列出所有商品。POST /v3/product/list",
            inputSchema={
                "type": "object",
                "properties": {
                    "last_id": {
                        "type": "string",
                        "description": "分页游标",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "每页数量",
                        "default": 100,
                    },
                    "visibility": {
                        "type": "string",
                        "description": "过滤: ALL / VISIBLE / INVISIBLE / ARCHIVED",
                    },
                },
            },
        ),
        Tool(
            name="ozon_product_import_info",
            description="查询 /v3/product/import 的结果状态。POST /v1/product/import/info",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "import 返回的 task_id",
                    }
                },
                "required": ["task_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        match name:
            case "ozon_category_tree":
                result = await ozon_post(
                    "/v1/description-category/tree",
                    {"language": arguments.get("language", "DEFAULT")},
                )

            case "ozon_category_attributes":
                result = await ozon_post(
                    "/v1/description-category/attribute",
                    {
                        "description_category_id": arguments["description_category_id"],
                        "type_id": arguments.get("type_id", 0),
                        "language": arguments.get("language", "DEFAULT"),
                    },
                )

            case "ozon_category_values":
                result = await ozon_post(
                    "/v1/description-category/attribute/values",
                    {
                        "attribute_id": arguments["attribute_id"],
                        "description_category_id": arguments["description_category_id"],
                        "type_id": arguments.get("type_id", 0),
                        "language": arguments.get("language", "DEFAULT"),
                        "last_value_id": arguments.get("last_value_id", 0),
                        "limit": arguments.get("limit", 5000),
                    },
                )

            case "ozon_product_import":
                result = await ozon_post(
                    "/v3/product/import",
                    {"items": arguments["items"]},
                )

            case "ozon_product_info":
                body: dict = {}
                if arguments.get("product_id"):
                    body["product_id"] = arguments["product_id"]
                if arguments.get("offer_id"):
                    body["offer_id"] = arguments["offer_id"]
                result = await ozon_post("/v3/product/info/list", body)

            case "ozon_product_list":
                body: dict = {"limit": arguments.get("limit", 100)}
                if arguments.get("last_id"):
                    body["last_id"] = arguments["last_id"]
                if arguments.get("visibility"):
                    body["filter"] = {"visibility": arguments["visibility"]}
                result = await ozon_post("/v3/product/list", body)

            case "ozon_product_import_info":
                result = await ozon_post(
                    "/v1/product/import/info",
                    {"task_id": arguments["task_id"]},
                )

            case _:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [
            TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2),
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


# ── Entry ───────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
