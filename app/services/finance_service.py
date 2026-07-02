"""Finance service — transaction sync and financial reporting."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from app.integrations.client import OzonClient
from app.integrations.endpoints.finance import FinanceEndpoints
from app.models.finance import FinanceTransaction
from app.models.order import Order

logger = logging.getLogger(__name__)


class FinanceService:
    """Manages financial transactions and P&L."""

    def __init__(self, db: AsyncSession, ozon_client: OzonClient | None = None) -> None:
        self.db = db
        self._endpoints: FinanceEndpoints | None = None
        if ozon_client:
            self._endpoints = FinanceEndpoints(ozon_client)

    @property
    def endpoints(self) -> FinanceEndpoints:
        if self._endpoints is None:
            raise RuntimeError("Ozon client not configured")
        return self._endpoints

    # ── Sync ──────────────────────────────────────────────────

    async def sync_transactions(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> int:
        """Pull finance transactions from Ozon. Returns count upserted."""
        if date_from is None:
            date_from = date.today() - timedelta(days=7)
        if date_to is None:
            date_to = date.today()

        operations = await self.endpoints.list_all_transactions(
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
        )

        count = 0
        for op in operations:
            op_id = op.get("operation_id", "")
            if not op_id:
                continue

            posting_number = (
                op.get("posting", {}).get("posting_number", "")
                if isinstance(op.get("posting"), dict)
                else None
            )

            # Find linked order
            order_id = None
            if posting_number:
                result = await self.db.execute(
                    select(Order.id).where(
                        Order.ozon_posting_number == posting_number
                    )
                )
                row = result.scalar_one_or_none()
                if row:
                    order_id = row

            stmt = insert(FinanceTransaction).values(
                ozon_operation_id=op_id,
                operation_type=op.get("operation_type", ""),
                operation_date=self._parse_dt(op.get("operation_date"))
                or datetime.now(),
                posting_number=posting_number,
                order_id=order_id,
                amount=float(op.get("amount", 0)),
                operation_type_name=op.get("operation_type_name"),
                accruals_for_sale=float(op.get("accruals_for_sale", 0) or 0),
                sale_commission=float(op.get("sale_commission", 0) or 0),
                delivery_charge=float(op.get("delivery_charge", 0) or 0),
                return_commission=float(op.get("return_commission", 0) or 0),
                raw_data=op,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["ozon_operation_id"],
                set_={
                    "amount": stmt.excluded.amount,
                    "accruals_for_sale": stmt.excluded.accruals_for_sale,
                    "sale_commission": stmt.excluded.sale_commission,
                    "delivery_charge": stmt.excluded.delivery_charge,
                    "return_commission": stmt.excluded.return_commission,
                    "raw_data": stmt.excluded.raw_data,
                },
            )
            await self.db.execute(stmt)
            count += 1

        # Update denormalized order P&L
        await self._recalculate_order_pnl(date_from, date_to)
        await self.db.commit()
        return count

    async def _recalculate_order_pnl(
        self, date_from: date, date_to: date
    ) -> None:
        """Recalculate denormalized financial fields on orders."""
        # Aggregate per posting_number
        result = await self.db.execute(
            select(
                FinanceTransaction.posting_number,
                func.sum(FinanceTransaction.accruals_for_sale),
                func.sum(FinanceTransaction.sale_commission),
            )
            .where(
                FinanceTransaction.operation_date >= date_from,
                FinanceTransaction.operation_date <= date_to,
                FinanceTransaction.posting_number.isnot(None),
            )
            .group_by(FinanceTransaction.posting_number)
        )
        for posting_number, accruals, commission in result.all():
            if posting_number:
                order_result = await self.db.execute(
                    select(Order).where(
                        Order.ozon_posting_number == posting_number
                    )
                )
                order = order_result.scalar_one_or_none()
                if order:
                    order.accruals_for_sale = float(accruals or 0)
                    order.commission_amount = float(commission or 0)

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

    # ── Queries ───────────────────────────────────────────────

    async def list_transactions(
        self,
        operation_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        posting_number: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[FinanceTransaction], int]:
        q = select(FinanceTransaction)
        count_q = select(func.count(FinanceTransaction.id))

        if operation_type:
            q = q.where(FinanceTransaction.operation_type == operation_type)
            count_q = count_q.where(FinanceTransaction.operation_type == operation_type)
        if date_from:
            q = q.where(FinanceTransaction.operation_date >= date_from)
            count_q = count_q.where(FinanceTransaction.operation_date >= date_from)
        if date_to:
            q = q.where(FinanceTransaction.operation_date <= date_to)
            count_q = count_q.where(FinanceTransaction.operation_date <= date_to)
        if posting_number:
            q = q.where(FinanceTransaction.posting_number == posting_number)
            count_q = count_q.where(FinanceTransaction.posting_number == posting_number)

        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        q = q.order_by(FinanceTransaction.operation_date.desc()).offset(offset).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def get_order_pnl(self, order_id: uuid.UUID) -> dict[str, Any]:
        """Calculate P&L for a single order."""
        order_result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = order_result.scalar_one_or_none()
        if not order:
            return {}

        txns_result = await self.db.execute(
            select(
                func.sum(FinanceTransaction.accruals_for_sale).label("accruals"),
                func.sum(FinanceTransaction.sale_commission).label("commission"),
                func.sum(FinanceTransaction.delivery_charge).label("delivery"),
                func.sum(FinanceTransaction.return_commission).label("returns_amount"),
                func.sum(FinanceTransaction.amount).label("total_amount"),
            ).where(FinanceTransaction.order_id == order_id)
        )
        row = txns_result.first()
        return {
            "order_id": str(order_id),
            "posting_number": order.ozon_posting_number,
            "total_price": float(order.total_price or 0),
            "total_amount": float(row.total_amount or 0) if row else 0,
            "accruals_for_sale": float(row.accruals or 0) if row else 0,
            "commission": float(row.commission or 0) if row else 0,
            "delivery_charge": float(row.delivery or 0) if row else 0,
            "return_commission": float(row.returns_amount or 0) if row else 0,
            "net_profit": order.net_profit,
        }

    async def get_period_summary(
        self, date_from: date, date_to: date
    ) -> dict[str, Any]:
        """Aggregated financial summary for a period."""
        result = await self.db.execute(
            select(
                func.sum(FinanceTransaction.amount).label("total"),
                func.sum(FinanceTransaction.accruals_for_sale).label("accruals"),
                func.sum(FinanceTransaction.sale_commission).label("commission"),
                func.sum(FinanceTransaction.delivery_charge).label("delivery"),
                func.sum(FinanceTransaction.return_commission).label("returns_amount"),
            ).where(
                FinanceTransaction.operation_date >= date_from,
                FinanceTransaction.operation_date <= date_to,
            )
        )
        row = result.first()
        accruals = float(row.accruals or 0) if row else 0
        commission = float(row.commission or 0) if row else 0
        delivery = float(row.delivery or 0) if row else 0
        returns_val = float(row.returns_amount or 0) if row else 0

        return {
            "period_from": date_from.isoformat(),
            "period_to": date_to.isoformat(),
            "total_amount": float(row.total or 0) if row else 0,
            "accruals_for_sale": accruals,
            "commission": commission,
            "delivery_charge": delivery,
            "returns": returns_val,
            "net_result": accruals - commission - delivery - returns_val,
        }
