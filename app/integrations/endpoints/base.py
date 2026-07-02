"""Base class for Ozon API endpoint wrappers."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from app.config import settings
from app.integrations.client import OzonClient

logger = logging.getLogger(__name__)


class BaseEndpoint:
    """Shared functionality for all Ozon API endpoint wrappers.

    - Auto-chunks large lists to respect Ozon batch limits.
    - Inserts delay between batch calls to avoid rate limiting.
    - Paginates cursor-based list endpoints transparently.
    """

    def __init__(self, client: OzonClient) -> None:
        self.client = client
        self.batch_delay = settings.OZON_BATCH_DELAY_SECONDS

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """POST to Ozon with the shared client."""
        return await self.client.post(path, body)

    async def _paginate_cursor(
        self,
        path: str,
        body_template: dict[str, Any],
        items_key: str = "items",
        cursor_key: str = "cursor",
        limit: int = 100,
    ) -> AsyncIterator[dict[str, Any]]:
        """Iterate over a cursor-paginated Ozon endpoint.

        Yields individual items one at a time.
        """
        cursor: str | None = None

        while True:
            body = {**body_template, "limit": limit}
            if cursor:
                body[cursor_key] = cursor

            result = await self._post(path, body)
            items: list[dict[str, Any]] = result.get(items_key, [])
            for item in items:
                yield item

            cursor = result.get(cursor_key)
            if not cursor or not items:
                break

    async def _paginate_offset(
        self,
        path: str,
        body_template: dict[str, Any],
        items_key: str = "result",
        total_key: str = "total",
        limit: int = 50,
    ) -> AsyncIterator[dict[str, Any]]:
        """Iterate over an offset-paginated Ozon endpoint."""
        offset = 0

        while True:
            body = {**body_template, "offset": offset, "limit": limit}
            result = await self._post(path, body)

            items: list[dict[str, Any]] = result.get(items_key, [])
            for item in items:
                yield item

            total: int = result.get(total_key, 0)
            offset += len(items)
            if offset >= total or not items:
                break
