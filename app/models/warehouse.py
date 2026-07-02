"""Warehouse model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.order import Order


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_rfbs: Mapped[bool] = mapped_column(Boolean, default=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    address: Mapped[str | None] = mapped_column(String(1000))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    stocks: Mapped[List["Stock"]] = relationship("Stock", back_populates="warehouse")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="warehouse")

    def __repr__(self) -> str:
        return f"<Warehouse id={self.id} name='{self.name}'>"
