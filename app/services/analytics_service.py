"""Analytics service — dashboard KPIs and reports."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.finance import FinanceTransaction
from app.models.product import Product
from app.models.stock import Stock

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Dashboard KPIs and analytical reports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_dashboard_kpis(self) -> dict[str, Any]:
        """Key performance indicators for the dashboard."""
        today = date.today()
        month_start = today.replace(day=1)
        week_start = today - timedelta(days=today.weekday())

        # Orders today / this week / this month
        orders_today = await self._count_orders(today, today)
        orders_week = await self._count_orders(week_start, today)
        orders_month = await self._count_orders(month_start, today)

        # Revenue (from finance transactions)
        revenue_today = await self._sum_transactions("accruals_for_sale", today, today)
        revenue_week = await self._sum_transactions("accruals_for_sale", week_start, today)
        revenue_month = await self._sum_transactions("accruals_for_sale", month_start, today)

        # Commission
        commission_month = await self._sum_transactions("sale_commission", month_start, today)

        # Product counts
        total_products_result = await self.db.execute(
            select(func.count(Product.id))
        )
        total_products = total_products_result.scalar() or 0

        active_products_result = await self.db.execute(
            select(func.count(Product.id)).where(Product.status == "imported")
        )
        active_products = active_products_result.scalar() or 0

        # Low stock count
        low_stock_result = await self.db.execute(
            select(func.count(func.distinct(Stock.product_id))).where(
                (Stock.present - Stock.reserved) <= 5
            )
        )
        low_stock = low_stock_result.scalar() or 0

        # Margin
        margin = (
            (revenue_month - commission_month) / revenue_month * 100
            if revenue_month > 0
            else 0
        )

        return {
            "orders": {
                "today": orders_today,
                "week": orders_week,
                "month": orders_month,
            },
            "revenue": {
                "today": float(revenue_today),
                "week": float(revenue_week),
                "month": float(revenue_month),
            },
            "commission_month": float(commission_month),
            "margin_pct": round(margin, 1),
            "products": {
                "total": total_products,
                "active": active_products,
                "low_stock": low_stock,
            },
            "currency": "RUB",
        }

    async def _count_orders(self, date_from: date, date_to: date) -> int:
        result = await self.db.execute(
            select(func.count(Order.id)).where(
                Order.created_at_ozon >= date_from,
                Order.created_at_ozon <= date_to + timedelta(days=1),
            )
        )
        return result.scalar() or 0

    async def _sum_transactions(
        self, field: str, date_from: date, date_to: date
    ) -> float:
        col = getattr(FinanceTransaction, field)
        result = await self.db.execute(
            select(func.sum(col)).where(
                FinanceTransaction.operation_date >= date_from,
                FinanceTransaction.operation_date <= date_to + timedelta(days=1),
            )
        )
        return float(result.scalar() or 0)

    # ── Sales Trend ───────────────────────────────────────────

    async def get_sales_trend(self, days: int = 30) -> list[dict[str, Any]]:
        """Daily sales for the last N days."""
        start = date.today() - timedelta(days=days - 1)
        result = await self.db.execute(
            select(
                func.date(FinanceTransaction.operation_date).label("day"),
                func.sum(FinanceTransaction.accruals_for_sale).label("revenue"),
                func.count(func.distinct(FinanceTransaction.posting_number)).label("orders"),
            )
            .where(
                FinanceTransaction.operation_date >= start,
                FinanceTransaction.operation_type == "Order accrual",
            )
            .group_by("day")
            .order_by("day")
        )
        return [
            {
                "date": str(row.day),
                "revenue": float(row.revenue or 0),
                "orders": int(row.orders or 0),
            }
            for row in result.all()
        ]

    # ── Top Products ──────────────────────────────────────────

    async def get_top_products(self, limit: int = 10) -> list[dict[str, Any]]:
        """Top-selling products by accruals (last 30 days)."""
        start = date.today() - timedelta(days=30)
        result = await self.db.execute(
            select(
                FinanceTransaction.posting_number,
                func.sum(FinanceTransaction.accruals_for_sale).label("total"),
                func.count(FinanceTransaction.id).label("txn_count"),
            )
            .where(
                FinanceTransaction.operation_date >= start,
                FinanceTransaction.operation_type == "Order accrual",
                FinanceTransaction.posting_number.isnot(None),
            )
            .group_by(FinanceTransaction.posting_number)
            .order_by(func.sum(FinanceTransaction.accruals_for_sale).desc())
            .limit(limit)
        )
        return [
            {
                "posting_number": row.posting_number,
                "total_accruals": float(row.total or 0),
                "transaction_count": row.txn_count,
            }
            for row in result.all()
        ]
