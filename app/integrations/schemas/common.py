"""Shared Pydantic models for Ozon API request/response structures."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


class OzonError(BaseModel):
    """Standard Ozon error response."""

    code: str = ""
    message: str = ""
    details: list[dict[str, Any]] = Field(default_factory=list)


class OzonResponse(BaseModel):
    """Generic wrapper for Ozon API responses that include a result field."""

    result: dict[str, Any] | list[Any] = Field(default_factory=dict)


# ── Pagination ───────────────────────────────────────────────────

T = TypeVar("T")


class PaginatedResult(BaseModel, Generic[T]):
    """Generic cursor-paginated result from Ozon."""

    items: list[T] = Field(default_factory=list)
    total: int = 0
    last_id: str | None = None  # Cursor for next page


# ── Shared types ─────────────────────────────────────────────────


class OzonImage(BaseModel):
    """Image reference for product import."""

    file_name: str
    default: bool = False


class OzonDimension(BaseModel):
    """Product dimensions in the Ozon format."""

    height: float | None = None  # mm
    depth: float | None = None  # mm
    width: float | None = None  # mm
    weight: float | None = None  # g


class TimestampRange(BaseModel):
    """Date range filter used across many Ozon endpoints."""

    since: datetime | None = None
    to: datetime | None = None
