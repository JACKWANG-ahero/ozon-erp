"""Async HTTP client for Ozon Seller API with auth, retry, and rate-limiting."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.integrations.rate_limiter import ozon_rate_limiter

logger = logging.getLogger(__name__)

# ── Exception hierarchy ───────────────────────────────────────────


class OzonAPIError(Exception):
    """Base for all Ozon API errors."""


class OzonAuthError(OzonAPIError):
    """401/403 — bad credentials."""


class OzonRateLimitError(OzonAPIError):
    """429 — rate limit exceeded (should not happen with rate limiter)."""


class OzonValidationError(OzonAPIError):
    """400 — invalid request body."""


class OzonNotFoundError(OzonAPIError):
    """404 — resource not found."""


class OzonServerError(OzonAPIError):
    """5xx — Ozon internal error."""


class OzonTimeoutError(OzonAPIError):
    """Request timeout."""


# ── Client ────────────────────────────────────────────────────────


class OzonClient:
    """Async HTTP client for the Ozon Seller API.

    - Injects ``Client-Id`` and ``Api-Key`` headers automatically.
    - Rate-limits through the shared ``TokenBucketRateLimiter``.
    - Retries on 429/5xx with exponential backoff.
    - Parses errors into typed exceptions.
    """

    def __init__(
        self,
        client_id: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.client_id = client_id or settings.OZON_CLIENT_ID
        self.api_key = api_key or settings.OZON_API_KEY
        self.base_url = (base_url or settings.OZON_BASE_URL).rstrip("/")

        if not self.client_id or not self.api_key:
            raise OzonAuthError(
                "OZON_CLIENT_ID and OZON_API_KEY must be set in .env or passed "
                "to the constructor."
            )

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Client-Id": self.client_id,
                    "Api-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Core request method ───────────────────────────────────

    async def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        timeout: float = 30.0,
        max_retries: int = 5,
    ) -> dict[str, Any]:
        """Send a request, auto-retrying on 429 with long backoff."""
        client = await self._get_client()
        url = f"{self.base_url}{path}"

        wait = 60  # start with 1 minute wait on first 429

        for attempt in range(max_retries + 1):
            # Rate-limit before each attempt
            async with ozon_rate_limiter:
                try:
                    response = await client.request(
                        method=method, url=url, json=body,
                        timeout=httpx.Timeout(timeout),
                    )
                except httpx.TimeoutException:
                    if attempt == max_retries:
                        raise OzonTimeoutError(f"Request to {path} timed out")
                    await asyncio_sleep(10)
                    continue

            if response.status_code < 400:
                ozon_rate_limiter.report_success()
                return response.json()

            # Error handling
            if response.status_code == 429:
                ozon_rate_limiter.report_429()
                if attempt < max_retries:
                    logger.warning(
                        "429 on %s, 第%d次重试, 等待%ds",
                        path, attempt + 1, wait,
                    )
                    await asyncio_sleep(wait)
                    wait = min(wait * 2, 300)  # 60s -> 120s -> 240s -> 300s
                    continue
                raise OzonRateLimitError(f"Ozon 限流，已重试{max_retries}次仍失败，请稍后再试")

            if response.status_code in (401, 403):
                raise OzonAuthError(f"Auth failed ({response.status_code}): {response.text[:500]}")
            if response.status_code == 400:
                raise OzonValidationError(f"Validation error on {path}: {response.text[:1000]}")
            if response.status_code == 404:
                raise OzonNotFoundError(f"Not found: {path}")
            if response.status_code >= 500:
                if attempt == max_retries:
                    raise OzonServerError(f"Server error ({response.status_code}): {response.text[:500]}")
                await asyncio_sleep(2 ** attempt)
                continue
            raise OzonAPIError(f"Unexpected {response.status_code} from {path}: {response.text[:500]}")

        raise OzonAPIError(f"Exhausted retries for {path}")

    # ── Convenience (all Ozon endpoints are POST) ─────────────

    async def post(
        self, path: str, body: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return await self.request("POST", path, body, **kwargs)


# asyncio.sleep alias for readability
def asyncio_sleep(seconds: float) -> "asyncio.Future[None]":
    import asyncio

    return asyncio.sleep(seconds)
