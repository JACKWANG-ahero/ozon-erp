"""Order, OrderItem, and OrderStatusHistory models.

Unified model for both FBS (Fulfillment by Seller) and FBO (Fulfillment by Ozon) orders.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy import Uuid as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.warehouse import Warehouse
    from app.models.finance import FinanceTransaction
    from app.models.return_model import Return
    from app.models.chat import Chat


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ozon_posting_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    order_number: Mapped[str | None] = mapped_column(String(100))
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'FBS' | 'FBO'

    # Status — Ozon raw status + normalized
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ozon_status: Mapped[str | None] = mapped_column(String(50))

    # Timestamps from Ozon
    in_process_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at_ozon: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Shipping
    shipment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(500))
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_express: Mapped[bool] = mapped_column(Boolean, default=False)
    warehouse_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("warehouses.id"))
    delivery_method: Mapped[str | None] = mapped_column(String(100))
    tracking_number: Mapped[str | None] = mapped_column(String(100))

    # ── Denormalized financial summary ────────────────────────
    total_price: Mapped[float | None] = mapped_column(Numeric(19, 4))
    commission_amount: Mapped[float | None] = mapped_column(Numeric(19, 4))
    accruals_for_sale: Mapped[float | None] = mapped_column(Numeric(19, 4))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    status_history: Mapped[List["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory", back_populates="order", cascade="all, delete-orphan"
    )
    warehouse: Mapped[Optional["Warehouse"]] = relationship("Warehouse", back_populates="orders")
    finance_transactions: Mapped[List["FinanceTransaction"]] = relationship(
        "FinanceTransaction", back_populates="order"
    )
    returns: Mapped[List["Return"]] = relationship("Return", back_populates="order")
    chats: Mapped[List["Chat"]] = relationship("Chat", back_populates="order")

    @property
    def net_profit(self) -> float | None:
        """Accruals minus commission."""
        if self.accruals_for_sale is not None and self.commission_amount is not None:
            return self.accruals_for_sale - self.commission_amount
        return None

    def __repr__(self) -> str:
        return (
            f"<Order posting='{self.ozon_posting_number}' "
            f"type={self.order_type} status='{self.status}'>"
        )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id")
    )
    offer_id: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped[Optional["Product"]] = relationship("Product", back_populates="order_items")

    def __repr__(self) -> str:
        return f"<OrderItem order={self.order_id} name='{self.name}' qty={self.quantity}>"


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    changed_by: Mapped[str | None] = mapped_column(String(50))
    # 'ozon_webhook' | 'user_action' | 'auto_sync'

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="status_history")

    def __repr__(self) -> str:
        return (
            f"<OrderStatusHistory order={self.order_id} "
            f"{self.from_status} -> {self.to_status}>"
        )
