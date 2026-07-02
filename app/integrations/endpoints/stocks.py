"""Ozon Stock API endpoint wrappers."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from app.config import settings
from app.integrations.client import OzonClient


class StockEndpoints:
    """Wraps /v2/products/stocks and /v4/product/info/stocks."""

    def __init__(self, client: OzonClient) -> None:
        self.client = client

    async def update_stocks(
        self, stocks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """POST /v2/products/stocks — batch update.

        Auto-chunks to 100 per call.
        """
        all_results: list[dict[str, Any]] = []

        for i in range(0, len(stocks), 100):
            if i > 0:
                await asyncio.sleep(settings.OZON_BATCH_DELAY_SECONDS)
            chunk = stocks[i : i + 100]
            result = await self.client.post(
                "/v2/products/stocks", {"stocks": chunk}
            )
            item_results: list[dict[str, Any]] = result.get("result", [])
            all_results.extend(item_results)

        return all_results

    async def get_stocks(
        self,
        product_ids: list[int] | None = None,
        offer_ids: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """POST /v4/product/info/stocks — cursor-paginated stock info."""
        cursor: str | None = None
        limit = 100

        while True:
            body: dict[str, Any] = {"limit": limit}
            if cursor:
                body["cursor"] = cursor
            if product_ids:
                body["product_id"] = product_ids[:100]
            if offer_ids:
                body["offer_id"] = offer_ids[:100]

            result = await self.client.post("/v4/product/info/stocks", body)
            res = result.get("result", {})
            items: list[dict[str, Any]] = res.get("items", [])
            for item in items:
                yield item

            cursor = res.get("cursor")
            if not cursor or not items:
                break
