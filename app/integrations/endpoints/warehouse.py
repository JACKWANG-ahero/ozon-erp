"""Ozon Warehouse API endpoint wrappers.

Covers:
- POST /v1/warehouse/list
- POST /v2/warehouse/list (fallback)
- POST /v1/delivery-method/list
"""

from __future__ import annotations

from typing import Any

from app.integrations.client import OzonClient


class WarehouseEndpoints:
    """Wraps /v1/warehouse/* and /v1/delivery-method/* endpoints."""

    def __init__(self, client: OzonClient) -> None:
        self.client = client

    async def list_warehouses(self) -> list[dict[str, Any]]:
        """POST /v1/warehouse/list — all FBS/rFBS warehouses.

        Falls back to /v2/warehouse/list if v1 is unavailable.
        """
        try:
            result = await self.client.post("/v1/warehouse/list")
            return result.get("result", [])
        except Exception:
            try:
                result = await self.client.post("/v2/warehouse/list")
                return result.get("result", [])
            except Exception:
                return []

    async def list_delivery_methods(
        self,
        warehouse_id: int | None = None,
        provider: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """POST /v1/delivery-method/list — Available delivery methods.

        Optional filters:
        - ``warehouse_id`` — filter by warehouse
        - ``provider`` — filter by delivery provider
        - ``status`` — filter by status (e.g. "ACTIVE")
        """
        body: dict[str, Any] = {}
        filt: dict[str, Any] = {}
        if warehouse_id:
            filt["warehouse_id"] = warehouse_id
        if provider:
            filt["provider"] = provider
        if status:
            filt["status"] = status
        if filt:
            body["filter"] = filt

        result = await self.client.post("/v1/delivery-method/list", body)
        return result.get("result", [])
