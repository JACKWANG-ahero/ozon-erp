"""Pydantic models for Ozon Order (Posting) API request/response."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── FBS: POST /v3/posting/fbs/list ───────────────────────────────


class FbsListFilter(BaseModel):
    """Filter for /v3/posting/fbs/list."""

    since: datetime | None = None
    to: datetime | None = None
    status: str | None = None  # awaiting_packaging | awaiting_deliver | delivering | delivered | cancelled
    warehouse_id: list[int] | None = None


class FbsListWith(BaseModel):
    """Optional includes."""

    analytics_data: bool = False
    financial_data: bool = False
    barcodes: bool = False


class FbsListRequest(BaseModel):
    """Body for /v3/posting/fbs/list."""

    filter: FbsListFilter = Field(default_factory=FbsListFilter)
    dir: str = "asc"
    offset: int = 0
    limit: int = 50
    with_: FbsListWith = Field(default_factory=FbsListWith, alias="with")


class FbsPostingProduct(BaseModel):
    """Single product in a posting."""

    price: str = ""
    offer_id: str = ""
    name: str = ""
    sku: int = 0
    quantity: int = 1
    currency_code: str = "RUB"


class FbsPostingItem(BaseModel):
    """A single FBS posting from the list."""

    posting_number: str = ""
    order_number: str = ""
    status: str = ""
    in_process_at: datetime | None = None
    created_at: datetime | None = None
    shipment_date: str | None = None
    delivery_date: str | None = None
    cancel_reason: str | None = None
    is_premium: bool = False
    is_express: bool = False
    warehouse_id: int = 0
    delivery_method: dict[str, Any] | None = None
    tracking_number: str | None = None
    products: list[FbsPostingProduct] = Field(default_factory=list)
    financial_data: dict[str, Any] | None = None
    analytics_data: dict[str, Any] | None = None


class FbsListResult(BaseModel):
    """Result from /v3/posting/fbs/list."""

    postings: list[FbsPostingItem] = Field(default_factory=list)
    total: int = 0


# ── FBS: POST /v3/posting/fbs/get ────────────────────────────────


class FbsGetRequest(BaseModel):
    """Body for /v3/posting/fbs/get."""

    posting_number: str


class FbsGetResult(BaseModel):
    """Full posting detail."""

    posting: FbsPostingItem | None = None


# ── FBS: POST /v3/posting/fbs/ship ───────────────────────────────


class FbsShipRequest(BaseModel):
    """Body for /v3/posting/fbs/ship."""

    posting_number: list[str]
    packages: list[dict[str, Any]] = Field(default_factory=list)


class FbsShipResult(BaseModel):
    """Per-posting result."""

    posting_number: str = ""
    status: str = ""
    errors: list[dict[str, Any]] = Field(default_factory=list)


# ── FBS state transitions ────────────────────────────────────────


class FbsStatusRequest(BaseModel):
    """Body for /v2/posting/fbs/delivering, /last-mile, /delivered."""

    posting_number: str


# ── FBS tracking number ──────────────────────────────────────────


class FbsTrackingRequest(BaseModel):
    """Body for /v2/posting/fbs/tracking-number/set."""

    posting_number: str
    tracking_number: str
    carrier: str = ""


# ── FBS label / act ──────────────────────────────────────────────


class FbsLabelRequest(BaseModel):
    """Body for /v2/posting/fbs/package-label."""

    posting_number: list[str]


class FbsActCreateRequest(BaseModel):
    """Body for /v2/posting/fbs/act/create."""

    posting_number: list[str]


# ── FBO: POST /v2/posting/fbo/list ───────────────────────────────


class FboListFilter(BaseModel):
    """Filter for /v2/posting/fbo/list."""

    since: datetime | None = None
    to: datetime | None = None
    status: str | None = None


class FboListRequest(BaseModel):
    """Body for /v2/posting/fbo/list."""

    filter: FboListFilter = Field(default_factory=FboListFilter)
    dir: str = "asc"
    offset: int = 0
    limit: int = 50


class FboPostingItem(BaseModel):
    """FBO posting from list."""

    posting_number: str = ""
    order_number: str = ""
    status: str = ""
    in_process_at: datetime | None = None
    created_at: datetime | None = None
    products: list[FbsPostingProduct] = Field(default_factory=list)
    analytics_data: dict[str, Any] | None = None
    financial_data: dict[str, Any] | None = None


class FboListResult(BaseModel):
    """Result from /v2/posting/fbo/list."""

    result: list[FboPostingItem] = Field(default_factory=list)
    total: int = 0
