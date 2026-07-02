"""Pydantic models for Ozon Product API request/response structures."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.integrations.schemas.common import OzonImage


# ── POST /v2/product/import ──────────────────────────────────────


class ProductImportAttribute(BaseModel):
    """Attribute value in import format."""

    id: int
    value: str = ""


class ProductImportItem(BaseModel):
    """Single product for /v2/product/import."""

    barcode: str | None = None
    category_id: int
    name: str
    offer_id: str
    price: str = "0"
    old_price: str = "0"
    premium_price: str = "0"
    vat: str = "0"
    vendor: str = ""
    vendor_code: str = ""
    images: list[OzonImage] = Field(default_factory=list)
    attributes: list[ProductImportAttribute] = Field(default_factory=list)
    height: float | None = None
    depth: float | None = None
    width: float | None = None
    weight: float | None = None
    description: str | None = None


class ProductImportRequest(BaseModel):
    """Body for /v2/product/import."""

    items: list[ProductImportItem]


class ProductImportResultItem(BaseModel):
    """Per-item result from import."""

    offer_id: str = ""
    product_id: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)
    updated: bool = False


class ProductImportResponse(BaseModel):
    """Response from /v2/product/import."""

    result: dict[str, Any] = Field(default_factory=dict)


# ── POST /v3/product/info/list ───────────────────────────────────


class ProductInfoListItem(BaseModel):
    """Product info item from /v3/product/info/list."""

    id: int = 0
    offer_id: str = ""
    name: str = ""
    barcode: str | None = None
    category_id: int = 0
    created_at: datetime | None = None
    images: list[str] = Field(default_factory=list)
    primary_image: str | None = None
    marketing_price: str | None = None
    min_price: str | None = None
    old_price: str | None = None
    premium_price: str | None = None
    price: str | None = None
    currency_code: str = "RUB"
    sources: list[dict[str, Any]] = Field(default_factory=list)
    stocks: dict[str, Any] | None = None
    skus: list[dict[str, Any]] = Field(default_factory=list)
    vat: str = "0"
    visible: bool = True
    volume_weight: float = 0.0
    status: str = ""
    errors: list[dict[str, Any]] = Field(default_factory=list)


class ProductInfoListRequest(BaseModel):
    """Body for /v3/product/info/list."""

    product_id: list[int] = Field(default_factory=list)
    offer_id: list[str] = Field(default_factory=list)
    sku: list[int] = Field(default_factory=list)


# ── POST /v3/product/list ────────────────────────────────────────


class ProductListRequest(BaseModel):
    """Body for /v3/product/list (paginated)."""

    last_id: str | None = None
    limit: int = 100
    filter: dict[str, Any] = Field(default_factory=dict)


class ProductListResult(BaseModel):
    """Result wrapper for /v3/product/list."""

    items: list[ProductInfoListItem] = Field(default_factory=list)
    total: int = 0
    last_id: str | None = None


# ── POST /v4/product/info/attributes ─────────────────────────────


class ProductAttributeRequest(BaseModel):
    """Body for /v4/product/info/attributes."""

    product_id: int
    language: str = "RU"


# ── POST /v1/product/info/description ────────────────────────────


class ProductDescriptionRequest(BaseModel):
    """Body for /v1/product/info/description."""

    product_id: int
    offer_id: str = ""


# ── POST /v1/product/classify ────────────────────────────────────


class ProductClassifyRequest(BaseModel):
    """Body for /v1/product/classify."""

    name: str
    description: str | None = None
    images: list[str] = Field(default_factory=list)


class ProductClassifyResult(BaseModel):
    """Suggested categories from auto-classification."""

    category_id: int = 0
    category_name: str = ""
    confidence: float = 0.0


# ── POST /v1/product/archive / unarchive ─────────────────────────


class ProductArchiveRequest(BaseModel):
    """Body for /v1/product/archive."""

    product_id: list[int] = Field(default_factory=list)
