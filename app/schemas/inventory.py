"""Pydantic schemas for Inventory API."""

from pydantic import BaseModel


class StockUpdateItem(BaseModel):
    product_id: str | None = None  # UUID
    offer_id: str | None = None
    stock: int
    warehouse_id: int


class StockUpdateRequest(BaseModel):
    stocks: list[StockUpdateItem]
