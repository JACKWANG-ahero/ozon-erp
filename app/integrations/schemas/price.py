"""Pydantic models for Ozon Price API request/response."""

from pydantic import BaseModel, Field


# ── POST /v1/product/import/prices ───────────────────────────────


class PriceImportItem(BaseModel):
    """Single price update."""

    offer_id: str | None = None
    product_id: int | None = None
    price: str  # "2990.00"
    old_price: str = "0"
    premium_price: str = "0"
    min_price: str = "0"
    auto_action_enabled: bool = False
    currency_code: str = "RUB"


class PriceImportRequest(BaseModel):
    """Body for /v1/product/import/prices."""

    prices: list[PriceImportItem]


class PriceImportResult(BaseModel):
    """Per-item result from price import."""

    product_id: int = 0
    offer_id: str = ""
    updated: bool = False
    errors: list[dict] = Field(default_factory=list)


# ── POST /v5/product/info/prices ─────────────────────────────────


class ProductPriceInfo(BaseModel):
    """Price info from /v5/product/info/prices."""

    product_id: int = 0
    offer_id: str = ""
    price: dict[str, str] = Field(default_factory=dict)
    price_index: str = "0"


class PriceInfoRequest(BaseModel):
    """Body for /v5/product/info/prices."""

    product_id: list[int] | None = None
    offer_id: list[str] | None = None
    cursor: str | None = None
    limit: int = 100


class PriceInfoResponse(BaseModel):
    """Response from /v5/product/info/prices."""

    items: list[ProductPriceInfo] = Field(default_factory=list)
    cursor: str | None = None
    total: int = 0
