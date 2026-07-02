"""Order service — FBS/FBO order lifecycle management."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.client import OzonClient
from app.integrations.endpoints.orders_fbs import FbsOrderEndpoints
from app.integrations.endpoints.orders_fbo import FboOrderEndpoints
from app.models.order import Order, OrderItem, OrderStatusHistory
from app.models.product import Product

logger = logging.getLogger(__name__)

FBS_STATUSES = [
    "awaiting_packaging",
    "awaiting_deliver",
    "delivering",
    "delivered",
    "cancelled",
]

FBO_STATUSES = [
    "awaiting_acceptance",
    "accepted",
    "in_warehouse",
    "in_delivery",
    "delivered",
    "cancelled",
]


class OrderService:
    """Order lifecycle management for FBS and FBO."""

    def __init__(self, db: AsyncSession, ozon_client: OzonClient | None = None) -> None:
        self.db = db
        self._fbs_ep: FbsOrderEndpoints | None = None
        self._fbo_ep: FboOrderEndpoints | None = None
        if ozon_client:
            self._fbs_ep = FbsOrderEndpoints(ozon_client)
            self._fbo_ep = FboOrderEndpoints(ozon_client)

    @property
    def fbs(self) -> FbsOrderEndpoints:
        if self._fbs_ep is None:
            raise RuntimeError("Ozon client not configured")
        return self._fbs_ep

    @property
    def fbo(self) -> FboOrderEndpoints:
        if self._fbo_ep is None:
            raise RuntimeError("Ozon client not configured")
        return self._fbo_ep

    # ── Pull ──────────────────────────────────────────────────

    async def pull_fbs_orders(
        self,
        since: datetime | None = None,
        status: str | None = None,
    ) -> int:
        """Pull FBS orders from Ozon. Returns count of orders processed."""
        if since is None:
            since = datetime.now() - timedelta(days=7)

        count = 0
        async for posting in self.fbs.list_postings(since=since, status=status):
            await self._upsert_order(posting, "FBS")
            count += 1

        await self.db.commit()
        return count

    async def pull_fbo_orders(
        self,
        since: datetime | None = None,
        status: str | None = None,
    ) -> int:
        """Pull FBO orders from Ozon. Returns count."""
        if since is None:
            since = datetime.now() - timedelta(days=7)

        count = 0
        async for posting in self.fbo.list_postings(since=since, status=status):
            await self._upsert_order(posting, "FBO")
            count += 1

        await self.db.commit()
        return count

    async def _upsert_order(self, posting: dict[str, Any], order_type: str) -> Order:
        """Insert or update a single order from Ozon data."""
        pn = posting.get("posting_number", "")
        existing = await self.db.execute(
            select(Order).where(Order.ozon_posting_number == pn)
        )
        order = existing.scalar_one_or_none()

        new_status = posting.get("status", "")

        if order:
            old_status = order.status
            if old_status != new_status:
                self.db.add(
                    OrderStatusHistory(
                        order_id=order.id,
                        from_status=old_status,
                        to_status=new_status,
                        changed_by="auto_sync",
                    )
                )
            order.status = new_status
            order.ozon_status = new_status
        else:
            order = Order(
                ozon_posting_number=pn,
                order_number=posting.get("order_number", ""),
                order_type=order_type,
                status=new_status,
                ozon_status=new_status,
                in_process_at=self._parse_dt(posting.get("in_process_at")),
                created_at_ozon=self._parse_dt(posting.get("created_at")),
                cancel_reason=posting.get("cancel_reason"),
                is_premium=posting.get("is_premium", False),
                is_express=posting.get("is_express", False),
                warehouse_id=posting.get("warehouse_id"),
                delivery_method=str(posting.get("delivery_method", {}).get("name", "")),
                tracking_number=posting.get("tracking_number"),
            )
            self.db.add(order)
            await self.db.flush()

            # Add order items
            for prod in posting.get("products", []):
                item = OrderItem(
                    order_id=order.id,
                    offer_id=prod.get("offer_id"),
                    sku=prod.get("sku"),
                    name=prod.get("name", ""),
                    quantity=prod.get("quantity", 1),
                    price=float(prod.get("price", "0") or "0"),
                )
                self.db.add(item)

        # Financial data (denormalized)
        fin_data = posting.get("financial_data", {}) or {}
        if fin_data:
            products_fin = fin_data.get("products", [])
            if products_fin:
                order.total_price = sum(
                    float(p.get("price", 0) or 0) for p in products_fin
                )
                order.commission_amount = sum(
                    float(p.get("commission_amount", 0) or 0) for p in products_fin
                )
                order.accruals_for_sale = sum(
                    float(p.get("accruals_for_sale", 0) or 0) for p in products_fin
                )

        order.last_synced_at = datetime.now()
        return order

    @staticmethod
    def _parse_dt(val: Any) -> datetime | None:
        if not val:
            return None
        if isinstance(val, datetime):
            return val
        try:
            return datetime.fromisoformat(str(val))
        except (ValueError, TypeError):
            return None

    # ── FBS Workflow ──────────────────────────────────────────

    async def ship_order(self, order_id: uuid.UUID) -> dict[str, Any]:
        """Ship an FBS order — transitions awaiting_packaging → awaiting_deliver."""
        order = await self._get_order(order_id)
        if not order or order.order_type != "FBS":
            return {"error": "Invalid order"}

        result = await self.fbs.ship([order.ozon_posting_number])
        if result and not result[0].get("errors"):
            self._record_status(order, "awaiting_deliver", "user_action")
            await self.db.commit()
        return result[0] if result else {}

    async def get_label(self, order_id: uuid.UUID) -> dict[str, Any]:
        """Get package label for an FBS order."""
        order = await self._get_order(order_id)
        if not order:
            return {"error": "Order not found"}
        return await self.fbs.get_label([order.ozon_posting_number])

    async def set_tracking(
        self, order_id: uuid.UUID, tracking_number: str, carrier: str = ""
    ) -> dict[str, Any]:
        """Set tracking number."""
        order = await self._get_order(order_id)
        if not order:
            return {"error": "Order not found"}

        result = await self.fbs.set_tracking_number(
            order.ozon_posting_number, tracking_number, carrier
        )
        if result:
            order.tracking_number = tracking_number
            await self.db.commit()
        return result

    async def mark_delivering(self, order_id: uuid.UUID) -> dict[str, Any]:
        order = await self._get_order(order_id)
        if not order:
            return {"error": "Order not found"}
        result = await self.fbs.set_status_delivering(order.ozon_posting_number)
        self._record_status(order, "delivering", "user_action")
        await self.db.commit()
        return result

    async def mark_delivered(self, order_id: uuid.UUID) -> dict[str, Any]:
        order = await self._get_order(order_id)
        if not order:
            return {"error": "Order not found"}
        result = await self.fbs.set_status_delivered(order.ozon_posting_number)
        self._record_status(order, "delivered", "user_action")
        await self.db.commit()
        return result

    def _record_status(self, order: Order, new_status: str, changed_by: str) -> None:
        old_status = order.status
        order.status = new_status
        self.db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=old_status,
                to_status=new_status,
                changed_by=changed_by,
            )
        )

    async def _get_order(self, order_id: uuid.UUID) -> Order | None:
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    # ── Queries ───────────────────────────────────────────────

    async def list_orders(
        self,
        order_type: str | None = None,
        status: str | None = None,
        since: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Order], int]:
        q = select(Order)
        count_q = select(func.count(Order.id))

        if order_type:
            q = q.where(Order.order_type == order_type)
            count_q = count_q.where(Order.order_type == order_type)
        if status:
            q = q.where(Order.status == status)
            count_q = count_q.where(Order.status == status)
        if since:
            q = q.where(Order.created_at_ozon >= since)
            count_q = count_q.where(Order.created_at_ozon >= since)

        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        q = q.order_by(Order.created_at_ozon.desc()).offset(offset).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def get_order_detail(self, order_id: uuid.UUID) -> Order | None:
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_order_status_history(self, order_id: uuid.UUID) -> list[OrderStatusHistory]:
        result = await self.db.execute(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.changed_at.desc())
        )
        return list(result.scalars().all())
