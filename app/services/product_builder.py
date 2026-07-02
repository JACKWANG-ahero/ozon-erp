"""Product builder — assemble OZON ProductImportItem from sourcing data."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.models.sourcing import SourcingRecord

logger = logging.getLogger(__name__)


class ProductBuilder:
    """Build Ozon-compatible product import items from sourcing records."""

    def __init__(self, category_id: int | None = None) -> None:
        self.category_id = category_id or settings.OZON_EMBROIDERY_CATEGORY_ID

    def build_import_items(
        self, record: SourcingRecord, target_price_rub: float | None = None
    ) -> list[dict[str, Any]]:
        """Build the payload for Ozon POST /v3/product/import.

        Creates one import item per SKU variation.

        Args:
            record: SourcingRecord with translated fields
            target_price_rub: Optional price in RUB. If None, uses cost_data.

        Returns:
            List of dicts ready for Ozon import API
        """
        if not self.category_id or self.category_id == 0:
            logger.warning(
                "OZON_EMBROIDERY_CATEGORY_ID not configured — "
                "using 0 (will need manual category assignment)"
            )

        # Use cost_data suggested price if no target provided
        if target_price_rub is None and record.cost_data:
            target_price_rub = (
                record.cost_data.get("result", {})
                .get("suggested_price_rub", 0)
            )

        # Build images list for Ozon (URL strings)
        images = record.images_ozon_urls or []
        if not images and record.images_local_paths:
            # Fallback: use 1688 CDN URLs directly
            images = record.images_1688_urls or []

        # Build offer_id prefix from article number or title
        offer_prefix = (record.article_number or record.title_cn[:10]).strip()
        offer_prefix = "".join(c for c in offer_prefix if c.isalnum() or c in "-_")[:20]

        items = []

        if record.skus:
            for i, sku in enumerate(record.skus):
                offer_id = f"{offer_prefix}-{i+1}" if len(record.skus) > 1 else offer_prefix

                item: dict[str, Any] = {
                    "offer_id": offer_id,
                    "name": record.title_ru or record.title_cn,
                    "description_category_id": self.category_id,
                    "type_id": 0,
                    "price": str(int(target_price_rub or 0)),
                    "old_price": str(int((target_price_rub or 0) * 1.15)),
                    "vat": "0",
                    "currency_code": "CNY",
                    "images": images[:15],
                    "primary_image": images[0] if images else "",
                    "images360": [],
                    "color_image": "",
                    "pdf_list": [],
                    "attributes": [],
                    "complex_attributes": [],
                    "depth": 0,
                    "height": 0,
                    "width": 0,
                    "weight": 0,
                    "dimension_unit": "mm",
                    "weight_unit": "g",
                    "new_description_category_id": 0,
                    "promotions": [],
                }

                # Dimensions (Ozon uses mm)
                if record.weight_kg:
                    item["weight"] = int(record.weight_kg * 1000)
                if record.length_cm:
                    item["depth"] = int(record.length_cm * 10)
                if record.width_cm:
                    item["width"] = int(record.width_cm * 10)
                if record.height_cm:
                    item["height"] = int(record.height_cm * 10)

                items.append(item)
        else:
            # Single item without SKU — v3 format
            item: dict[str, Any] = {
                "offer_id": offer_prefix or "new-product",
                "name": record.title_ru or record.title_cn,
                "description_category_id": self.category_id,
                "type_id": 0,
                "price": str(int(target_price_rub or 0)),
                "old_price": str(int((target_price_rub or 0) * 1.15)),
                "vat": "0",
                "currency_code": "CNY",
                "images": images[:15],
                "primary_image": images[0] if images else "",
                "images360": [],
                "color_image": "",
                "pdf_list": [],
                "attributes": [],
                "complex_attributes": [],
                "depth": 0,
                "height": 0,
                "width": 0,
                "weight": 0,
                "dimension_unit": "mm",
                "weight_unit": "g",
                "new_description_category_id": 0,
                "promotions": [],
            }
            if record.weight_kg:
                item["weight"] = int(record.weight_kg * 1000)
            if record.length_cm:
                item["depth"] = int(record.length_cm * 10)
            if record.width_cm:
                item["width"] = int(record.width_cm * 10)
            if record.height_cm:
                item["height"] = int(record.height_cm * 10)

            items.append(item)

        return items
