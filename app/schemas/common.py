"""Shared Pydantic schemas for the ERP API."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""

    items: list[T] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    code: str | None = None


class SuccessResponse(BaseModel):
    """Generic success response."""

    ok: bool = True
    message: str = ""
    data: dict[str, Any] | None = None
