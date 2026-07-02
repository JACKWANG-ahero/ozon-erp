"""Inventory service — stock tracking and sync with Ozon."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from app.integrations.client import OzonClient
from app.integrations.endpoints.stocks import StockEndpoints
from app.integrations.endpoints.warehouse import WarehouseEndpoints
from app.models.stock import Stock
from app.models.warehouse import Warehouse
from app.models.product import Product

logger = logging.getLogger(__name__)


class InventoryService:
    """Manages warehouse stocks, synced from/to Ozon."""

    def __init__(self, db: AsyncSession, ozon_client: OzonClient | None = None) -> None:
        self.db = db
        self._stock_ep: StockEndpoints | None = None
        self._wh_ep: WarehouseEndpoints | None = None
        if ozon_client:
            self._stock_ep = StockEndpoints(ozon_client)
            self._wh_ep = WarehouseEndpoints(ozon_client)

    @property
    def stock_endpoints(self) -> StockEndpoints:
        if self._stock_ep is None:
            raise RuntimeError("Ozon client not configured")
        return self._stock_ep

    @property
    def warehouse_endpoints(self) -> WarehouseEndpoints:
        if self._wh_ep is None:
            raise RuntimeError("Ozon client not configured")
        return self._wh_ep

    # ── Warehouse Sync ────────────────────────────────────────

    async def sync_warehouses(self) -> int:
        """Pull warehouse list from Ozon."""
        warehouses = await self.warehouse_endpoints.list_warehouses()
        count = 0
        for wh in warehouses:
            stmt = insert(Warehouse).values(
                id=wh["warehouse_id"],
                name=wh.get("name", ""),
                is_rfbs=wh.get("is_rfbs", False),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={"name": stmt.excluded.name, "is_rfbs": stmt.excluded.is_rfbs},
            )
            await self.db.execute(stmt)
            count += 1
        await self.db.commit()
        return count

    # ── Stock Pull ────────────────────────────────────────────

    async def pull_stocks(
        self, product_ids: list[int] | None = None
    ) -> int:
        """Pull stock levels from Ozon. Returns count of stock records updated."""
        count = 0
        async for item in self.stock_endpoints.get_stocks(product_ids=product_ids):
            pid = item.get("product_id")
            for s in item.get("stocks", []):
                warehouse_id = s.get("warehouse_id")
                present = s.get("present", 0)
                reserved = s.get("reserved", 0)

                # Find local product
                from app.models.product import Product
                result = await self.db.execute(
                    select(Product).where(Product.ozon_product_id == pid)
                )
                product = result.scalar_one_or_none()
                if not product:
                    continue

                stmt = insert(Stock).values(
                    product_id=product.id,
                    warehouse_id=warehouse_id,
                    present=present,
                    reserved=reserved,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["product_id", "warehouse_id"],
                    set_={
                        "present": stmt.excluded.present,
                        "reserved": stmt.excluded.reserved,
                    },
                )
                await self.db.execute(stmt)
                count += 1

        await self.db.commit()
        return count

    # ── Stock Push ────────────────────────────────────────────

    async def push_stocks(
        self, stocks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Push stock updates to Ozon. Each entry: {'product_id' or 'offer_id', 'stock', 'warehouse_id'}."""
        payload = []
        for s in stocks:
            item: dict[str, Any] = {
                "stock": s["stock"],
                "warehouse_id": s["warehouse_id"],
            }
            if s.get("product_id"):
                item["product_id"] = s["product_id"]
            elif s.get("offer_id"):
                item["offer_id"] = s["offer_id"]
            else:
                continue
            payload.append(item)

        return await self.stock_endpoints.update_stocks(payload)

    # ── Queries ───────────────────────────────────────────────

    async def get_stocks_by_product(
        self, product_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        """Get stock levels for a product across all warehouses."""
        result = await self.db.execute(
            select(Stock, Warehouse.name)
            .join(Warehouse, Stock.warehouse_id == Warehouse.id)
            .where(Stock.product_id == product_id)
        )
        rows = result.all()
        return [
            {
                "warehouse_id": s.warehouse_id,
                "warehouse_name": name,
                "present": s.present,
                "reserved": s.reserved,
                "available": s.available,
            }
            for s, name in rows
        ]

    async def get_low_stock_products(
        self, threshold: int = 5
    ) -> list[dict[str, Any]]:
        """Find products with low available stock."""
        result = await self.db.execute(
            select(Stock, Product.name_ru, Product.offer_id)
            .join(Product, Stock.product_id == Product.id)
            .where((Stock.present - Stock.reserved) <= threshold)
            .order_by(Stock.present)
        )
        rows = result.all()
        return [
            {
                "product_id": s.product_id,
                "offer_id": offer_id,
                "name": name,
                "warehouse_id": s.warehouse_id,
                "present": s.present,
                "reserved": s.reserved,
                "available": s.available,
            }
            for s, name, offer_id in rows
        ]

    async def get_warehouses(self) -> list[Warehouse]:
        result = await self.db.execute(select(Warehouse).order_by(Warehouse.name))
        return list(result.scalars().all())
