"""Ozon Finance API endpoint wrappers."""

from __future__ import annotations

from typing import Any

from app.integrations.client import OzonClient


class FinanceEndpoints:
    """Wraps /v3/finance/transaction/list and /v3/finance/transaction/totals."""

    def __init__(self, client: OzonClient) -> None:
        self.client = client

    async def list_transactions(
        self,
        date_from: str,
        date_to: str,
        operation_type: list[str] | None = None,
        posting_number: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """POST /v3/finance/transaction/list."""
        body: dict[str, Any] = {
            "filter": {
                "date": {"from": date_from, "to": date_to},
                "transaction_type": "all",
            },
            "page": page,
            "page_size": page_size,
        }
        if operation_type:
            body["filter"]["operation_type"] = operation_type
        if posting_number:
            body["filter"]["posting_number"] = posting_number

        return await self.client.post("/v3/finance/transaction/list", body)

    async def list_all_transactions(
        self,
        date_from: str,
        date_to: str,
        operation_type: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Paginate through all transactions in the date range."""
        all_ops: list[dict[str, Any]] = []
        page = 1

        while True:
            result = await self.list_transactions(
                date_from=date_from,
                date_to=date_to,
                operation_type=operation_type,
                page=page,
                page_size=100,
            )
            operations: list[dict[str, Any]] = result.get("result", {}).get(
                "operations", []
            )
            all_ops.extend(operations)

            page_count: int = result.get("result", {}).get("page_count", 1)
            if page >= page_count or not operations:
                break
            page += 1

        return all_ops

    async def get_totals(
        self, date_from: str, date_to: str
    ) -> dict[str, Any]:
        """POST /v3/finance/transaction/totals."""
        return await self.client.post(
            "/v3/finance/transaction/totals",
            {"date": {"from": date_from, "to": date_to}},
        )
