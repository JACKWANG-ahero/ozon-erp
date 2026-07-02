"""Stock model — inventory per product per warehouse."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy import Uuid as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.warehouse import Warehouse


class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_stock_product_warehouse"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id"), nullable=False
    )

    present: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="stocks")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="stocks")

    @property
    def available(self) -> int:
        """Stock available for sale (present - reserved)."""
        return max(0, self.present - self.reserved)

    def __repr__(self) -> str:
        return (
            f"<Stock product={self.product_id} warehouse={self.warehouse_id} "
            f"present={self.present}>"
        )
