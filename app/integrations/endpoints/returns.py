"""Ozon Returns API endpoint wrappers."""

from __future__ import annotations

from typing import Any

from app.integrations.client import OzonClient


class ReturnEndpoints:
    """Wraps /v1/returns/list and /v1/returns/get."""

    def __init__(self, client: OzonClient) -> None:
        self.client = client

    async def list_returns(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """POST /v1/returns/list."""
        body: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            body["filter"] = {"status": status}
        return await self.client.post("/v1/returns/list", body)

    async def get_return(self, return_id: int) -> dict[str, Any]:
        """POST /v1/returns/get."""
        return await self.client.post(
            "/v1/returns/get", {"return_id": return_id}
        )
