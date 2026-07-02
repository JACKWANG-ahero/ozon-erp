"""Ozon FBS Order (Posting) API endpoint wrappers.

Covers:
- POST /v3/posting/fbs/list
- POST /v3/posting/fbs/get
- POST /v3/posting/fbs/unfulfilled/list
- POST /v3/posting/fbs/ship
- POST /v2/posting/fbs/package-label
- POST /v2/posting/fbs/act/create
- POST /v2/posting/fbs/delivering
- POST /v2/posting/fbs/last-mile
- POST /v2/posting/fbs/delivered
- POST /v2/posting/fbs/tracking-number/set
- POST /v2/posting/fbs/cancel
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, AsyncIterator

from app.integrations.client import OzonClient

logger = logging.getLogger(__name__)


class FbsOrderEndpoints:
    """Wraps all /v*/posting/fbs/* endpoints."""

    def __init__(self, client: OzonClient) -> None:
        self.client = client

    async def list_postings(
        self,
        since: datetime | None = None,
        to: datetime | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> AsyncIterator[dict[str, Any]]:
        """POST /v3/posting/fbs/list — offset-paginated.

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

            result = await self.client.post("/v3/posting/fbs/list", body)
            postings: list[dict[str, Any]] = result.get("result", {}).get(
                "postings", []
            )
            for p in postings:
                yield p

            total: int = result.get("result", {}).get("total", 0)
            offset += len(postings)
            if offset >= total or not postings:
                break

    async def get_posting(self, posting_number: str) -> dict[str, Any]:
        """POST /v3/posting/fbs/get."""
        result = await self.client.post(
            "/v3/posting/fbs/get", {"posting_number": posting_number}
        )
        return result.get("result", {}).get("posting", {})

    async def list_unfulfilled(self, status: str | None = None) -> list[dict[str, Any]]:
        """POST /v3/posting/fbs/unfulfilled/list."""
        body: dict[str, Any] = {}
        if status:
            body["status"] = status
        result = await self.client.post(
            "/v3/posting/fbs/unfulfilled/list", body
        )
        return result.get("result", {}).get("postings", [])

    async def ship(
        self, posting_numbers: list[str], packages: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """POST /v3/posting/fbs/ship."""
        body: dict[str, Any] = {"posting_number": posting_numbers}
        if packages:
            body["packages"] = packages
        result = await self.client.post("/v3/posting/fbs/ship", body)
        return result.get("result", [])

    async def get_label(self, posting_numbers: list[str]) -> dict[str, Any]:
        """POST /v2/posting/fbs/package-label — returns label PDF URL."""
        return await self.client.post(
            "/v2/posting/fbs/package-label",
            {"posting_number": posting_numbers},
        )

    async def create_act(self, posting_numbers: list[str]) -> dict[str, Any]:
        """POST /v2/posting/fbs/act/create."""
        return await self.client.post(
            "/v2/posting/fbs/act/create",
            {"posting_number": posting_numbers},
        )

    async def set_status_delivering(self, posting_number: str) -> dict[str, Any]:
        """POST /v2/posting/fbs/delivering."""
        return await self.client.post(
            "/v2/posting/fbs/delivering",
            {"posting_number": posting_number},
        )

    async def set_status_last_mile(self, posting_number: str) -> dict[str, Any]:
        """POST /v2/posting/fbs/last-mile."""
        return await self.client.post(
            "/v2/posting/fbs/last-mile",
            {"posting_number": posting_number},
        )

    async def set_status_delivered(self, posting_number: str) -> dict[str, Any]:
        """POST /v2/posting/fbs/delivered."""
        return await self.client.post(
            "/v2/posting/fbs/delivered",
            {"posting_number": posting_number},
        )

    async def set_tracking_number(
        self, posting_number: str, tracking_number: str, carrier: str = ""
    ) -> dict[str, Any]:
        """POST /v2/posting/fbs/tracking-number/set."""
        return await self.client.post(
            "/v2/posting/fbs/tracking-number/set",
            {
                "posting_number": posting_number,
                "tracking_number": tracking_number,
                "carrier": carrier,
            },
        )

    async def cancel(self, posting_number: str, reason: str = "") -> dict[str, Any]:
        """POST /v2/posting/fbs/cancel."""
        body: dict[str, Any] = {"posting_number": posting_number}
        if reason:
            body["cancel_reason"] = reason
        return await self.client.post("/v2/posting/fbs/cancel", body)
