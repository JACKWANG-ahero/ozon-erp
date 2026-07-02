"""Pydantic schemas for Order API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OrderItemResponse(BaseModel):
    id: UUID
    offer_id: str | None = None
    sku: int | None = None
    name: str
    quantity: int
    price: float

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: UUID
    ozon_posting_number: str
    order_number: str | None = None
    order_type: str
    status: str
    in_process_at: datetime | None = None
    created_at_ozon: datetime | None = None
    shipment_date: str | None = None
    delivery_date: str | None = None
    warehouse_id: int | None = None
    tracking_number: str | None = None
    total_price: float | None = None
    commission_amount: float | None = None
    accruals_for_sale: float | None = None
    items: list[OrderItemResponse] = []

    model_config = {"from_attributes": True}


class TrackingUpdate(BaseModel):
    tracking_number: str
    carrier: str = ""
