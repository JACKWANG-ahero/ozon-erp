"""SyncService — orchestrates all Ozon ↔ local DB synchronization."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.client import OzonClient
from app.models.sync_log import SyncLog
from app.services.category_service import CategoryService
from app.services.product_service import ProductService
from app.services.inventory_service import InventoryService
from app.services.price_service import PriceService
from app.services.order_service import OrderService
from app.services.finance_service import FinanceService

logger = logging.getLogger(__name__)


class SyncService:
    """Central orchestrator for all data synchronization.

    Tracks every sync operation in the ``sync_log`` table so operators
    can audit what happened and when.
    """

    def __init__(self, db: AsyncSession, ozon_client: OzonClient | None = None) -> None:
        self.db = db
        self.client = ozon_client

    # ── Sync Log Helpers ──────────────────────────────────────

    async def _start_log(self, entity_type: str, direction: str) -> SyncLog:
        log = SyncLog(
            entity_type=entity_type,
            direction=direction,
            status="running",
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def _finish_log(
        self,
        log: SyncLog,
        status: str,
        processed: int = 0,
        failed: int = 0,
        error: str | None = None,
    ) -> None:
        log.completed_at = datetime.now()
        log.status = status
        log.records_processed = processed
        log.records_failed = failed
        log.error_message = error
        try:
            await self.db.commit()
        except Exception:
            logger.exception("Failed to commit sync log")

    async def _run_sync(
        self,
        entity_type: str,
        direction: str,
        coro: Any,
    ) -> SyncLog:
        """Run a sync coroutine wrapped in logging.

        Returns the SyncLog entry.
        """
        log = await self._start_log(entity_type, direction)
        try:
            result = await coro
            count = result if isinstance(result, int) else 0
            await self._finish_log(log, "success", processed=count)
        except Exception as e:
            logger.exception("Sync %s/%s failed", entity_type, direction)
            await self._finish_log(log, "failed", error=str(e))
        return log

    # ── Pull Syncs (Ozon → Local) ─────────────────────────────

    async def sync_categories(self) -> SyncLog:
        svc = CategoryService(self.db, self.client)
        return await self._run_sync("category", "pull", svc.sync_category_tree())

    async def sync_warehouses(self) -> SyncLog:
        svc = InventoryService(self.db, self.client)
        return await self._run_sync("warehouse", "pull", svc.sync_warehouses())

    async def sync_products_pull(self) -> SyncLog:
        svc = ProductService(self.db, self.client)
        return await self._run_sync("product", "pull", svc.pull_product_info())

    async def sync_products_push(self, product_ids: list | None = None) -> SyncLog:
        """Push modified/draft products to Ozon."""
        svc = ProductService(self.db, self.client)

        async def _push() -> int:
            if product_ids:
                result = await svc.import_to_ozon(product_ids)
                return result.get("success", 0)
            else:
                # Push all modified products
                from sqlalchemy import select
                from app.models.product import Product

                q = select(Product).where(
                    Product.sync_status.in_(["local_only", "modified"]),
                    Product.status.in_(["draft", "import_error", "imported"]),
                )
                result = await self.db.execute(q)
                products = result.scalars().all()
                if not products:
                    return 0
                res = await svc.import_to_ozon([p.id for p in products])
                return res.get("success", 0)

        return await self._run_sync("product", "push", _push())

    async def sync_prices(self) -> SyncLog:
        svc = PriceService(self.db, self.client)
        return await self._run_sync("price", "pull", svc.pull_prices())

    async def sync_stocks(self) -> SyncLog:
        svc = InventoryService(self.db, self.client)
        return await self._run_sync("stock", "pull", svc.pull_stocks())

    async def sync_fbs_orders(self) -> SyncLog:
        svc = OrderService(self.db, self.client)
        return await self._run_sync("order", "pull", svc.pull_fbs_orders())

    async def sync_fbo_orders(self) -> SyncLog:
        svc = OrderService(self.db, self.client)
        return await self._run_sync("order", "pull", svc.pull_fbo_orders())

    async def sync_finance(self) -> SyncLog:
        svc = FinanceService(self.db, self.client)
        return await self._run_sync("finance", "pull", svc.sync_transactions())

    # ── Full Sync ─────────────────────────────────────────────

    async def full_sync(self) -> list[SyncLog]:
        """Run all pull syncs in sequence. Returns list of log entries."""
        logs: list[SyncLog] = []
        for name, method in [
            ("categories", self.sync_categories),
            ("warehouses", self.sync_warehouses),
            ("products", self.sync_products_pull),
            ("prices", self.sync_prices),
            ("stocks", self.sync_stocks),
            ("fbs_orders", self.sync_fbs_orders),
            ("fbo_orders", self.sync_fbo_orders),
            ("finance", self.sync_finance),
        ]:
            logger.info("Full sync: starting %s", name)
            log = await method()
            logs.append(log)
        return logs

    # ── Query ─────────────────────────────────────────────────

    async def get_sync_history(
        self, entity_type: str | None = None, limit: int = 50
    ) -> list[SyncLog]:
        from sqlalchemy import select

        q = select(SyncLog).order_by(SyncLog.started_at.desc()).limit(limit)
        if entity_type:
            q = q.where(SyncLog.entity_type == entity_type)
        result = await self.db.execute(q)
        return list(result.scalars().all())
