"""Price and PriceHistory models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy import Uuid as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.product import Product


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), unique=True, nullable=False
    )

    price: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)  # Selling price (RUB)
    old_price: Mapped[float | None] = mapped_column(Numeric(19, 4))  # "Before discount"
    min_price: Mapped[float | None] = mapped_column(Numeric(19, 4))  # Auto-strategy floor
    premium_price: Mapped[float | None] = mapped_column(Numeric(19, 4))
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    vat: Mapped[str] = mapped_column(String(10), default="0")  # 0, 0.05, 0.07, 0.1, 0.2
    is_auto_strategy: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    # manual | ozon | strategy

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="price")

    def __repr__(self) -> str:
        return (
            f"<Price product={self.product_id} price={self.price} RUB>"
        )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )

    price: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    old_price: Mapped[float | None] = mapped_column(Numeric(19, 4))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    changed_by: Mapped[str | None] = mapped_column(String(50))
    # 'manual' | 'ozon_sync' | 'strategy'

    def __repr__(self) -> str:
        return (
            f"<PriceHistory product={self.product_id} price={self.price} "
            f"at={self.changed_at}>"
        )
