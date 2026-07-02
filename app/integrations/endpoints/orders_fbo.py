"""Ozon FBO Order (Posting) API endpoint wrappers.

Covers:
- POST /v2/posting/fbo/list
- POST /v2/posting/fbo/get
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncIterator

from app.integrations.client import OzonClient


class FboOrderEndpoints:
    """Wraps /v2/posting/fbo/* endpoints."""

    def __init__(self, client: OzonClient) -> None:
        self.client = client

    async def list_postings(
        self,
        since: datetime | None = None,
        to: datetime | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> AsyncIterator[dict[str, Any]]:
        """POST /v2/posting/fbo/list — offset-paginated.

        Yields individual posting dicts.
        """
        offset = 0
        while True:
            body: dict[str, Any] = {
                "dir": "asc",
                "offset": offset,
                "limit": limit,
            }
            flt: dict[str, Any] = {}
            if since:
                flt["since"] = since.isoformat()
            if to:
                flt["to"] = to.isoformat()
            if status:
                flt["status"] = status
            if flt:
                body["filter"] = flt

            result = await self.client.post("/v2/posting/fbo/list", body)
            postings: list[dict[str, Any]] = result.get("result", [])
            for p in postings:
                yield p

            total: int = result.get("total", 0)
            offset += len(postings)
            if offset >= total or not postings:
                break

    async def get_posting(self, posting_number: str) -> dict[str, Any]:
        """POST /v2/posting/fbo/get."""
        result = await self.client.post(
            "/v2/posting/fbo/get", {"posting_number": posting_number}
        )
        return result.get("result", {})
