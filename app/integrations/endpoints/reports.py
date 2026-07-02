"""Ozon Reports API endpoint wrappers."""

from __future__ import annotations

from typing import Any

from app.integrations.client import OzonClient


class ReportEndpoints:
    """Wraps /v1/report/list, /v1/report/info, /v1/report/create."""

    def __init__(self, client: OzonClient) -> None:
        self.client = client

    async def list_reports(self) -> list[dict[str, Any]]:
        """POST /v1/report/list — available generated reports."""
        result = await self.client.post("/v1/report/list")
        return result.get("result", [])

    async def get_report_info(self, report_code: str) -> dict[str, Any]:
        """POST /v1/report/info."""
        return await self.client.post(
            "/v1/report/info", {"code": report_code}
        )

    async def create_report(
        self,
        report_type: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        """POST /v1/report/create — request report generation."""
        return await self.client.post(
            "/v1/report/create",
            {
                "report_type": report_type,
                "date_from": date_from,
                "date_to": date_to,
            },
        )
