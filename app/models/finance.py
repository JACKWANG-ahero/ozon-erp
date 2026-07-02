"""FinanceTransaction model — Ozon financial operations."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy import JSON as JSONB
from sqlalchemy import Uuid as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.order import Order


class FinanceTransaction(Base):
    __tablename__ = "finance_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ozon_operation_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    operation_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Order accrual | Commission | Return | Delivery | Adjustment | ...
    operation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    posting_number: Mapped[str | None] = mapped_column(String(100), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id"), index=True
    )

    # Financial breakdown
    amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    operation_type_name: Mapped[str | None] = mapped_column(String(500))
    accruals_for_sale: Mapped[float | None] = mapped_column(Numeric(19, 4))
    sale_commission: Mapped[float | None] = mapped_column(Numeric(19, 4))
    delivery_charge: Mapped[float | None] = mapped_column(Numeric(19, 4))
    return_commission: Mapped[float | None] = mapped_column(Numeric(19, 4))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")

    # Full raw response from Ozon
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    order: Mapped[Optional["Order"]] = relationship(
        "Order", back_populates="finance_transactions"
    )

    def __repr__(self) -> str:
        return (
            f"<FinanceTransaction op_id='{self.ozon_operation_id}' "
            f"type='{self.operation_type}' amount={self.amount}>"
        )
