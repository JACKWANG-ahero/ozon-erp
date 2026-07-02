"""Return model — product returns from customers."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy import Uuid as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.product import Product


class Return(Base):
    __tablename__ = "returns"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ozon_return_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    posting_number: Mapped[str | None] = mapped_column(String(100), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), index=True
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    return_reason: Mapped[str | None] = mapped_column(String(500))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float | None] = mapped_column(Numeric(19, 4))

    return_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    order: Mapped[Optional["Order"]] = relationship("Order", back_populates="returns")
    product: Mapped[Optional["Product"]] = relationship("Product", back_populates="returns")

    def __repr__(self) -> str:
        return f"<Return id={self.ozon_return_id} status='{self.status}'>"
