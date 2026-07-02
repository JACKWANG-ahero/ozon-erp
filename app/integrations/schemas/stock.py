"""Pydantic models for Ozon Stock API request/response."""

from pydantic import BaseModel, Field


# ── POST /v2/products/stocks ─────────────────────────────────────


class StockUpdateItem(BaseModel):
    """Single stock update for /v2/products/stocks."""

    offer_id: str | None = None
    product_id: int | None = None
    stock: int
    warehouse_id: int


class StockUpdateRequest(BaseModel):
    """Body for /v2/products/stocks."""

    stocks: list[StockUpdateItem]


class StockUpdateResult(BaseModel):
    """Per-item result."""

    product_id: int = 0
    offer_id: str = ""
    updated: bool = False
    errors: list[dict] = Field(default_factory=list)


# ── POST /v4/product/info/stocks ─────────────────────────────────


class StockInfoItem(BaseModel):
    """Stock info entry for a single warehouse."""

    warehouse_id: int = 0
    warehouse_name: str = ""
    present: int = 0
    reserved: int = 0


class ProductStockInfo(BaseModel):
    """Stock info for one product across warehouses."""

    product_id: int = 0
    offer_id: str = ""
    stocks: list[StockInfoItem] = Field(default_factory=list)


class StockInfoRequest(BaseModel):
    """Body for /v4/product/info/stocks."""

    product_id: list[int] | None = None
    offer_id: list[str] | None = None
    cursor: str | None = None
    limit: int = 100


class StockInfoResponse(BaseModel):
    """Response from /v4/product/info/stocks."""

    items: list[ProductStockInfo] = Field(default_factory=list)
    cursor: str | None = None
    total: int = 0
