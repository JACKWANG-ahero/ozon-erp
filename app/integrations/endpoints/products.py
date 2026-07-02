"""Ozon Product API endpoint wrappers.

Covers:
- POST /v3/product/import (create/update)
- POST /v1/product/import/info (import status)
- POST /v1/product/import/by_sku (copy by SKU)
- POST /v1/product/import/pictures (upload images)
- POST /v1/product/update/attributes (update attributes)
- POST /v1/product/update/offer_id (change offer_id)
- POST /v3/product/info/list (batch info)
- POST /v3/product/list (paginated catalog)
- POST /v4/product/info/attributes (full attributes)
- POST /v1/product/info/description (HTML description)
- POST /v1/product/classify (auto-classify)
- POST /v1/product/archive / unarchive
- POST /v2/products/delete (delete from archive)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from app.config import settings
from app.integrations.client import OzonClient

logger = logging.getLogger(__name__)


class ProductEndpoints:
    """Wraps all /v*/product/* endpoints."""

    def __init__(self, client: OzonClient) -> None:
        self.client = client

    # ── Import / Update ───────────────────────────────────────

    async def import_products(
        self, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """POST /v3/product/import — batch create/update products.

        Ozon v3 import is asynchronous:
        1. POST /v3/product/import → returns ``task_id``
        2. POST /v1/product/import/info → poll with task_id for per-item results

        Auto-chunks into 100 items per call (Ozon limit).
        Returns a flat list of per-item result dicts (from the info endpoint).
        """
        chunk_size = 100
        all_results: list[dict[str, Any]] = []

        for i in range(0, len(items), chunk_size):
            if i > 0:
                await asyncio.sleep(settings.OZON_BATCH_DELAY_SECONDS)
            chunk = items[i : i + chunk_size]
            resp = await self.client.post(
                "/v3/product/import", {"items": chunk}
            )
            task_id: str | None = resp.get("result", {}).get("task_id")
            if not task_id:
                # Fallback: some responses may return inline results
                inline = resp.get("result", {}).get("items", [])
                if inline:
                    all_results.extend(inline)
                    continue
                logger.warning("No task_id in import response: %s", resp)
                continue

            # Poll for results
            item_results = await self._poll_import_info(task_id)
            all_results.extend(item_results)

        return all_results

    async def _poll_import_info(
        self, task_id: str, max_retries: int = 30, delay: float = 2.0
    ) -> list[dict[str, Any]]:
        """Poll POST /v1/product/import/info until the task completes.

        Returns the per-item result list on success.
        """
        for attempt in range(1, max_retries + 1):
            await asyncio.sleep(delay)
            resp = await self.client.post(
                "/v1/product/import/info", {"task_id": task_id}
            )
            result = resp.get("result", {})
            items = result.get("items", [])
            status = result.get("status", "")

            if status in ("completed", "success", ""):
                # Empty status or completed — check if items are ready
                if items and all(
                    i.get("product_id") or i.get("errors") for i in items
                ):
                    return items
            elif status in ("failed", "error"):
                logger.error("Import task %s failed: %s", task_id, result)
                return items or []

            logger.debug(
                "Import task %s poll %d/%d, status=%s",
                task_id, attempt, max_retries, status,
            )

        logger.warning("Import task %s timed out after %d polls", task_id, max_retries)
        return []

    async def get_import_info(self, task_id: str) -> dict[str, Any]:
        """POST /v1/product/import/info — single poll for import status."""
        resp = await self.client.post(
            "/v1/product/import/info", {"task_id": task_id}
        )
        return resp.get("result", {})

    # ── Batch info ────────────────────────────────────────────

    async def get_product_info_list(
        self, product_ids: list[int] | None = None, offer_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """POST /v3/product/info/list — get info for up to 100 products.

        Auto-chunks to 100 IDs per call.
        """
        ids = product_ids or []
        oids = offer_ids or []
        all_items: list[dict[str, Any]] = []

        # Chunk by product_id (max 100)
        for i in range(0, len(ids), 100):
            if i > 0:
                await asyncio.sleep(settings.OZON_BATCH_DELAY_SECONDS)
            chunk = ids[i : i + 100]
            body: dict[str, Any] = {"product_id": chunk}
            result = await self.client.post("/v3/product/info/list", body)
            items: list[dict[str, Any]] = result.get("result", {}).get("items", [])
            all_items.extend(items)

        # Also fetch by offer_id if provided
        if oids:
            for i in range(0, len(oids), 100):
                if all_items:  # delay after product_id batch
                    await asyncio.sleep(settings.OZON_BATCH_DELAY_SECONDS)
                chunk = oids[i : i + 100]
                result = await self.client.post(
                    "/v3/product/info/list", {"offer_id": chunk}
                )
                items: list[dict[str, Any]] = result.get("result", {}).get("items", [])
                # Avoid duplicates
                seen = {item.get("id") for item in all_items}
                for item in items:
                    if item.get("id") not in seen:
                        all_items.append(item)

        return all_items

    # ── Paginated catalog ─────────────────────────────────────

    async def list_all_products(
        self, status: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """POST /v3/product/list — iterate over all products.

        Handles cursor pagination transparently.
        """
        last_id: str | None = None
        limit = 100

        while True:
            body: dict[str, Any] = {"limit": limit}
            if last_id:
                body["last_id"] = last_id
            if status:
                body["filter"] = {"visibility": status}

            result = await self.client.post("/v3/product/list", body)
            res = result.get("result", {})
            items: list[dict[str, Any]] = res.get("items", [])
            for item in items:
                yield item

            last_id = res.get("last_id")
            if not last_id or not items:
                break

    # ── Attributes ────────────────────────────────────────────

    async def get_product_attributes(
        self, product_id: int, language: str = "RU"
    ) -> dict[str, Any]:
        """POST /v4/product/info/attributes."""
        result = await self.client.post(
            "/v4/product/info/attributes",
            {"product_id": product_id, "language": language},
        )
        return result.get("result", {})

    # ── Description ───────────────────────────────────────────

    async def get_product_description(
        self, product_id: int | None = None, offer_id: str | None = None
    ) -> str:
        """POST /v1/product/info/description."""
        body: dict[str, Any] = {}
        if product_id:
            body["product_id"] = product_id
        if offer_id:
            body["offer_id"] = offer_id
        result = await self.client.post("/v1/product/info/description", body)
        return result.get("result", {}).get("description", "")

    # ── Classify ──────────────────────────────────────────────

    async def classify_product(
        self, name: str, description: str | None = None
    ) -> list[dict[str, Any]]:
        """POST /v1/product/classify — suggest categories."""
        body: dict[str, Any] = {"name": name}
        if description:
            body["description"] = description
        result = await self.client.post("/v1/product/classify", body)
        return result.get("result", [])

    # ── Archive / Unarchive ───────────────────────────────────

    async def archive_products(self, product_ids: list[int]) -> dict[str, Any]:
        """POST /v1/product/archive."""
        return await self.client.post(
            "/v1/product/archive", {"product_id": product_ids}
        )

    async def unarchive_products(self, product_ids: list[int]) -> dict[str, Any]:
        """POST /v1/product/unarchive."""
        return await self.client.post(
            "/v1/product/unarchive", {"product_id": product_ids}
        )

    # ── Upload Images ───────────────────────────────────────────

    async def upload_images(
        self,
        offer_id: str,
        images: list[str] | None = None,
        primary_image: str | None = None,
        color_image: str | None = None,
    ) -> dict[str, Any]:
        """POST /v1/product/import/pictures — Upload/update product images.

        Images must be publicly accessible HTTPS URLs (JPG/PNG).
        Ozon downloads them and assigns to the product identified by ``offer_id``.
        Up to 15 images per call.
        """
        body: dict[str, Any] = {"offer_id": offer_id}
        if images:
            body["images"] = images
        if primary_image:
            body["primary_image"] = primary_image
        if color_image:
            body["color_image"] = color_image
        return await self.client.post("/v1/product/import/pictures", body)

    # ── Update Attributes ───────────────────────────────────────

    async def update_attributes(
        self,
        offer_id: str,
        attributes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """POST /v1/product/update/attributes — Update product attribute values.

        ``attributes`` format::

            [{"id": 8229, "value": "4747"}]

        Complex attributes use ``values`` array with ``dictionary_value_id``.
        """
        return await self.client.post(
            "/v1/product/update/attributes",
            {"offer_id": offer_id, "attributes": attributes},
        )

    # ── Import by SKU ───────────────────────────────────────────

    async def import_by_sku(self, skus: list[str]) -> dict[str, Any]:
        """POST /v1/product/import/by_sku — Create product cards from existing SKUs.

        Creates copies of product cards with the specified SKUs.
        """
        return await self.client.post(
            "/v1/product/import/by_sku",
            {"sku": skus},
        )

    # ── Update Offer ID ─────────────────────────────────────────

    async def update_offer_id(
        self, updates: list[dict[str, str]]
    ) -> dict[str, Any]:
        """POST /v1/product/update/offer_id — Change offer_id(s).

        ``updates`` format::

            [{"offer_id": "OLD-001", "new_offer_id": "NEW-001"}]
        """
        return await self.client.post(
            "/v1/product/update/offer_id",
            {"updates": updates},
        )

    # ── Delete Products ─────────────────────────────────────────

    async def delete_products(
        self, product_ids: list[int]
    ) -> dict[str, Any]:
        """POST /v2/products/delete — Delete products without SKUs from archive.

        Max 500 IDs per request.
        """
        return await self.client.post(
            "/v2/products/delete", {"product_id": product_ids}
        )
