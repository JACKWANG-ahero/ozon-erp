"""Pydantic schemas for Product API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProductAttributeSchema(BaseModel):
    attribute_id: int
    value_string: str | None = None
    value_int: int | None = None
    value_numeric: float | None = None
    value_json: dict[str, Any] | None = None


class ProductCreate(BaseModel):
    offer_id: str
    name_ru: str
    name_zh: str | None = None
    description_ru: str | None = None
    description_zh: str | None = None
    category_id: int | None = None
    brand: str | None = None
    barcode: str | None = None
    height: float | None = None
    depth: float | None = None
    width: float | None = None
    weight: float | None = None
    primary_image_url: str | None = None
    attributes: list[ProductAttributeSchema] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    name_ru: str | None = None
    name_zh: str | None = None
    description_ru: str | None = None
    description_zh: str | None = None
    category_id: int | None = None
    brand: str | None = None
    barcode: str | None = None
    height: float | None = None
    depth: float | None = None
    width: float | None = None
    weight: float | None = None
    primary_image_url: str | None = None


class ProductResponse(BaseModel):
    id: UUID
    ozon_product_id: int | None = None
    offer_id: str
    name_ru: str
    name_zh: str | None = None
    category_id: int | None = None
    brand: str | None = None
    barcode: str | None = None
    status: str
    sync_status: str
    primary_image_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
