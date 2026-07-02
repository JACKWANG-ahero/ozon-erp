"""Price service — price management and Ozon sync."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from app.integrations.client import OzonClient
from app.integrations.endpoints.prices import PriceEndpoints
from app.models.price import Price, PriceHistory
from app.models.product import Product

logger = logging.getLogger(__name__)


class PriceService:
    """Manages product prices, synced with Ozon."""

    def __init__(self, db: AsyncSession, ozon_client: OzonClient | None = None) -> None:
        self.db = db
        self._endpoints: PriceEndpoints | None = None
        if ozon_client:
            self._endpoints = PriceEndpoints(ozon_client)

    @property
    def endpoints(self) -> PriceEndpoints:
        if self._endpoints is None:
            raise RuntimeError("Ozon client not configured")
        return self._endpoints

    # ── Pull ──────────────────────────────────────────────────

    async def pull_prices(
        self, product_ids: list[int] | None = None
    ) -> int:
        """Pull prices from Ozon. Returns count updated."""
        count = 0
        async for item in self.endpoints.get_prices(product_ids=product_ids):
            ozon_product_id = item.get("product_id")
            offer_id = item.get("offer_id", "")
            price_data = item.get("price", {})

            # Find local product
            product = None
            if ozon_product_id:
                result = await self.db.execute(
                    select(Product).where(Product.ozon_product_id == ozon_product_id)
                )
                product = result.scalar_one_or_none()
            if not product and offer_id:
                result = await self.db.execute(
                    select(Product).where(Product.offer_id == offer_id)
                )
                product = result.scalar_one_or_none()

            if not product:
                continue

            old_price_value = float(price_data.get("old_price", "0") or "0")
            price_value = float(price_data.get("price", "0") or "0")

            # Check if price changed
            existing = await self.db.execute(
                select(Price).where(Price.product_id == product.id)
            )
            current_price = existing.scalar_one_or_none()

            if current_price:
                if current_price.price != price_value or current_price.old_price != old_price_value:
                    # Record history
                    self.db.add(
                        PriceHistory(
                            product_id=product.id,
                            price=price_value,
                            old_price=old_price_value,
                            changed_by="ozon_sync",
                        )
                    )

            # Upsert
            stmt = insert(Price).values(
                product_id=product.id,
                price=price_value,
                old_price=old_price_value,
                min_price=float(price_data.get("min_price", "0") or "0"),
                premium_price=float(price_data.get("premium_price", "0") or "0"),
                currency=price_data.get("currency_code", "RUB"),
                source="ozon",
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["product_id"],
                set_={
                    "price": stmt.excluded.price,
                    "old_price": stmt.excluded.old_price,
                    "min_price": stmt.excluded.min_price,
                    "premium_price": stmt.excluded.premium_price,
                },
            )
            await self.db.execute(stmt)
            count += 1

        await self.db.commit()
        return count

    # ── Push ──────────────────────────────────────────────────

    async def push_prices(
        self, prices: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Push price updates to Ozon.

        Each entry::
            {
                'product_id' or 'offer_id': ...,
                'price': 2990.00,
                'old_price': 3490.00 (optional),
                'min_price': 2590.00 (optional),
            }
        """
        payload = []
        for p in prices:
            item: dict[str, Any] = {
                "price": str(p["price"]),
                "old_price": str(p.get("old_price", p["price"])),
                "min_price": str(p.get("min_price", p["price"])),
                "currency_code": "RUB",
            }
            if p.get("product_id"):
                item["product_id"] = p["product_id"]
            elif p.get("offer_id"):
                item["offer_id"] = p["offer_id"]
            else:
                continue
            payload.append(item)

        return await self.endpoints.update_prices(payload)

    # ── Local Update ──────────────────────────────────────────

    async def update_price(
        self, product_id: uuid.UUID, price: float, old_price: float | None = None
    ) -> Price | None:
        """Update local price. Sets source='manual'."""
        existing = await self.db.execute(
            select(Price).where(Price.product_id == product_id)
        )
        current = existing.scalar_one_or_none()

        if current:
            # Record history
            self.db.add(
                PriceHistory(
                    product_id=product_id,
                    price=price,
                    old_price=old_price,
                    changed_by="manual",
                )
            )
            current.price = price
            if old_price is not None:
                current.old_price = old_price
            current.source = "manual"
            current.updated_at = datetime.now()
        else:
            current = Price(
                product_id=product_id,
                price=price,
                old_price=old_price or price,
                source="manual",
            )
            self.db.add(current)

        await self.db.commit()
        return current

    async def bulk_update_prices(
        self, updates: list[dict[str, Any]]
    ) -> int:
        """Bulk update local prices and optionally push to Ozon.

        Each entry: {'product_id': UUID, 'price': float, 'old_price': float | None, 'push': bool}
        """
        count = 0
        to_push = []
        for u in updates:
            pid = u["product_id"]
            price = float(u["price"])
            old = u.get("old_price")
            await self.update_price(pid, price, old)
            count += 1
            if u.get("push", True):
                product = await self.db.execute(
                    select(Product).where(Product.id == pid)
                )
                p = product.scalar_one_or_none()
                if p and p.ozon_product_id:
                    to_push.append(
                        {
                            "product_id": p.ozon_product_id,
                            "price": price,
                            "old_price": old or price,
                        }
                    )

        if to_push:
            await self.push_prices(to_push)

        await self.db.commit()
        return count

    # ── Query ─────────────────────────────────────────────────

    async def get_price_history(
        self, product_id: uuid.UUID, limit: int = 50
    ) -> list[PriceHistory]:
        result = await self.db.execute(
            select(PriceHistory)
            .where(PriceHistory.product_id == product_id)
            .order_by(PriceHistory.changed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_prices_batch(self, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, Price]:
        """Get prices for multiple products at once."""
        result = await self.db.execute(
            select(Price).where(Price.product_id.in_(product_ids))
        )
        return {p.product_id: p for p in result.scalars().all()}
