"""Product service — local product CRUD + Ozon sync."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.client import OzonClient
from app.integrations.endpoints.products import ProductEndpoints
from app.models.product import Product, ProductAttribute, ProductImage

logger = logging.getLogger(__name__)


class ProductService:
    """CRUD for the local product catalog. Pushes to Ozon on import."""

    def __init__(self, db: AsyncSession, ozon_client: OzonClient | None = None) -> None:
        self.db = db
        self._endpoints: ProductEndpoints | None = None
        if ozon_client:
            self._endpoints = ProductEndpoints(ozon_client)

    @property
    def endpoints(self) -> ProductEndpoints:
        if self._endpoints is None:
            raise RuntimeError("Ozon client not configured")
        return self._endpoints

    # ── Local CRUD ────────────────────────────────────────────

    async def create_product(self, data: dict[str, Any]) -> Product:
        """Create a product in the local catalog (status='draft')."""
        product = Product(
            offer_id=data["offer_id"],
            name_ru=data.get("name_ru", ""),
            name_zh=data.get("name_zh"),
            description_ru=data.get("description_ru"),
            description_zh=data.get("description_zh"),
            category_id=data.get("category_id"),
            brand=data.get("brand"),
            barcode=data.get("barcode"),
            height=data.get("height"),
            depth=data.get("depth"),
            width=data.get("width"),
            weight=data.get("weight"),
            primary_image_url=data.get("primary_image_url"),
            keywords=data.get("keywords"),
            status="draft",
            sync_status="local_only",
        )
        self.db.add(product)
        await self.db.flush()

        # Attributes
        for attr in data.get("attributes", []):
            pa = ProductAttribute(
                product_id=product.id,
                attribute_id=attr["attribute_id"],
                value_string=attr.get("value_string"),
                value_int=attr.get("value_int"),
                value_numeric=attr.get("value_numeric"),
                value_json=attr.get("value_json"),
            )
            self.db.add(pa)

        # Images
        for i, img_url in enumerate(data.get("images", [])):
            pi = ProductImage(
                product_id=product.id,
                url=img_url if isinstance(img_url, str) else img_url.get("url", ""),
                is_primary=(i == 0),
                sort_order=i,
            )
            self.db.add(pi)

        # Price record (v3 API required fields)
        from app.models.price import Price
        price = Price(
            product_id=product.id,
            price=data.get("price", "0"),
            old_price=data.get("old_price", "0"),
            vat=data.get("vat", "0"),
            currency=data.get("currency_code", "CNY"),
            source="manual",
        )
        self.db.add(price)

        await self.db.commit()
        return product

    async def update_product(self, product_id: uuid.UUID, data: dict[str, Any]) -> Product | None:
        """Update a product. Sets sync_status='modified' if already synced."""
        product = await self.get_by_id(product_id)
        if not product:
            return None

        for field in (
            "name_ru", "name_zh", "description_ru", "description_zh",
            "category_id", "brand", "barcode",
            "height", "depth", "width", "weight",
            "primary_image_url",
        ):
            if field in data:
                setattr(product, field, data[field])

        if product.sync_status == "synced":
            product.sync_status = "modified"

        await self.db.commit()
        return product

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        from sqlalchemy.orm import selectinload
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.images),
                selectinload(Product.attributes),
                selectinload(Product.category),
                selectinload(Product.price),
            )
            .where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_by_offer_id(self, offer_id: str) -> Product | None:
        result = await self.db.execute(
            select(Product).where(Product.offer_id == offer_id)
        )
        return result.scalar_one_or_none()

    async def list_products(
        self,
        status: str | None = None,
        category_id: int | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        """List products with optional filters. Returns (items, total)."""
        from sqlalchemy.orm import selectinload
        q = select(Product).options(selectinload(Product.price))
        count_q = select(func.count(Product.id))

        if status:
            q = q.where(Product.status == status)
            count_q = count_q.where(Product.status == status)
        if category_id:
            q = q.where(Product.category_id == category_id)
            count_q = count_q.where(Product.category_id == category_id)
        if search:
            like = f"%{search}%"
            q = q.where(
                (Product.name_ru.ilike(like))
                | (Product.name_zh.ilike(like))
                | (Product.offer_id.ilike(like))
                | (Product.brand.ilike(like))
            )
            count_q = count_q.where(
                (Product.name_ru.ilike(like))
                | (Product.name_zh.ilike(like))
                | (Product.offer_id.ilike(like))
                | (Product.brand.ilike(like))
            )

        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        q = q.order_by(Product.updated_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(q)
        items = list(result.scalars().all())

        return items, total

    # ── Ozon Import (Push) ────────────────────────────────────

    async def import_to_ozon(self, product_ids: list[uuid.UUID]) -> dict[str, Any]:
        """Push selected products to Ozon.

        Returns: {'success': N, 'failed': N, 'errors': [...]}
        """
        from sqlalchemy.orm import selectinload
        from app.models.category import Category

        # Eager-load images, attributes, category, and price to avoid MissingGreenlet
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.images),
                selectinload(Product.attributes),
                selectinload(Product.category),
                selectinload(Product.price),
            )
            .where(Product.id.in_(product_ids))
        )
        all_products = list(result.scalars().all())

        products = []
        for p in all_products:
            if p.status in ("draft", "import_error"):
                products.append(p)
            elif p.sync_status == "modified":
                products.append(p)

        if not products:
            return {"success": 0, "failed": 0, "errors": []}

        # Validate: Ozon requires at least 1 image per product
        no_image_products = [p for p in products if not p.images]
        if no_image_products:
            skus = [p.offer_id for p in no_image_products]
            return {
                "success": 0,
                "failed": len(no_image_products),
                "errors": [
                    {
                        "offer_id": sku,
                        "errors": [{"code": "NO_IMAGE", "message": "商品图片为必填项，请先添加至少1张图片"}],
                    }
                    for sku in skus
                ],
            }

        # Fetch categories for type_id lookup
        cat_ids = {p.category_id for p in products if p.category_id}
        cat_map: dict[int, Any] = {}
        if cat_ids:
            cat_result = await self.db.execute(
                select(Category).where(Category.id.in_(cat_ids))
            )
            for cat in cat_result.scalars().all():
                cat_map[cat.id] = cat

        items = [
            self._to_ozon_import_format(
                p, cat_map.get(p.category_id),
                price_str=str(p.price.price) if p.price and p.price.price else "0",
                old_price_str=str(p.price.old_price) if p.price and p.price.old_price else "0",
                vat_str=str(p.price.vat) if p.price and p.price.vat else "0",
                currency_str=str(p.price.currency) if p.price and p.price.currency else "CNY",
            )
            for p in products
        ]
        results = await self.endpoints.import_products(items)

        # Build result map by offer_id (async import may not preserve order)
        result_map: dict[str, dict[str, Any]] = {}
        for r in results:
            oid = r.get("offer_id", "")
            if oid:
                result_map[oid] = r

        success = 0
        failed = 0
        errors = []

        for p in products:
            r = result_map.get(p.offer_id, {})
            if not r:
                failed += 1
                p.status = "import_error"
                p.import_errors = {"errors": [{"code": "NO_RESULT", "message": "Ozon 未返回此商品的结果"}]}
                errors.append({"offer_id": p.offer_id, "errors": [{"code": "NO_RESULT", "message": "Ozon 未返回此商品的结果"}]})
            elif r.get("errors"):
                failed += 1
                p.status = "import_error"
                p.import_errors = {"errors": r["errors"]}
                errors.append({"offer_id": p.offer_id, "errors": r["errors"]})
            else:
                success += 1
                p.ozon_product_id = r.get("product_id")
                p.status = "imported"
                p.sync_status = "synced"
                p.import_errors = None

        await self.db.commit()
        return {"success": success, "failed": failed, "errors": errors}

    def _to_ozon_import_format(
        self, product: Product, category: Any = None,
        price_str: str = "0", old_price_str: str = "0", vat_str: str = "0",
        currency_str: str = "CNY",
    ) -> dict[str, Any]:
        """Map local Product model → Ozon /v3/product/import item format.

        v3 JSON schema (matches official docs):
        - ``description_category_id`` (NOT ``category_id``)
        - ``type_id`` — required, from category tree
        - ``images`` is a list of URL strings (not objects)
        - ``attributes`` uses ``values`` array with ``dictionary_value_id`` + ``value``
        - No ``vendor``, no ``description`` at item level
        """
        # v3: images are plain URL strings
        images = [img.url for img in product.images]
        primary_image = images[0] if images else ""

        # v3 attributes format: {id, complex_id, values: [{dictionary_value_id?, value}]}
        # Per official example:
        #   - Dictionary-based: {"dictionary_value_id": 971082156, "value": "麦克风架"}
        #   - Text-based:       {"value": "一套X3NFC保护膜..."}
        attributes = []
        for attr in product.attributes:
            val = (
                attr.value_string
                or (str(attr.value_int) if attr.value_int is not None else None)
                or (str(attr.value_numeric) if attr.value_numeric is not None else None)
                or ""
            )
            # Only include dictionary_value_id for numeric dictionary references
            if val.isdigit():
                attr_item: dict[str, Any] = {
                    "complex_id": 0,
                    "id": attr.attribute_id,
                    "values": [
                        {"dictionary_value_id": int(val), "value": val}
                    ],
                }
            else:
                attr_item = {
                    "complex_id": 0,
                    "id": attr.attribute_id,
                    "values": [
                        {"value": val}
                    ],
                }
            attributes.append(attr_item)

        # Required: depth/height/width/weight must be numbers (not None)
        height = float(product.height) if product.height else 0
        depth = float(product.depth) if product.depth else 0
        width = float(product.width) if product.width else 0
        weight = float(product.weight) if product.weight else 0

        # type_id from category lookup (must be integer, never None)
        type_id = (category.type_id or 0) if category else 0

        return {
            "offer_id": product.offer_id,
            "name": product.name_ru or product.name_zh or "",
            "description_category_id": product.category_id or 0,
            "type_id": type_id,
            "barcode": product.barcode or "",
            "price": price_str,
            "old_price": old_price_str,
            "vat": vat_str,
            "currency_code": currency_str,
            "images": images,
            "primary_image": primary_image,
            "images360": [],
            "color_image": "",
            "pdf_list": [],
            "attributes": attributes,
            "complex_attributes": [],
            "height": height,
            "depth": depth,
            "width": width,
            "weight": weight,
            "dimension_unit": "mm",
            "weight_unit": "g",
            "new_description_category_id": 0,
            "promotions": [],
        }

    # ── Ozon Pull ─────────────────────────────────────────────

    async def pull_product_info(
        self, product_ids: list[int] | None = None
    ) -> int:
        """Pull product info from Ozon into local DB. Returns count synced."""
        items = await self.endpoints.get_product_info_list(product_ids=product_ids or [])
        count = 0

        for item in items:
            ozon_id = item.get("id")
            if not ozon_id:
                continue

            # Find existing by ozon_product_id or offer_id
            product = None
            result = await self.db.execute(
                select(Product).where(Product.ozon_product_id == ozon_id)
            )
            product = result.scalar_one_or_none()

            if not product:
                offer_id = item.get("offer_id", "")
                if offer_id:
                    result = await self.db.execute(
                        select(Product).where(Product.offer_id == offer_id)
                    )
                    product = result.scalar_one_or_none()

            if not product:
                # Create new from Ozon
                product = Product(
                    offer_id=item.get("offer_id") or f"ozon-{ozon_id}",
                    ozon_product_id=ozon_id,
                    name_ru=item.get("name", ""),
                    category_id=item.get("category_id"),
                    barcode=item.get("barcode"),
                    status="imported",
                    sync_status="synced",
                    ozon_visibility="VISIBLE" if item.get("visible") else "INVISIBLE",
                )
                self.db.add(product)
            elif product.sync_status != "modified":
                # Update local (Ozon wins unless local has pending changes)
                product.name_ru = item.get("name", product.name_ru)
                product.category_id = item.get("category_id", product.category_id)
                product.barcode = item.get("barcode", product.barcode)
                product.ozon_product_id = ozon_id
                product.ozon_visibility = "VISIBLE" if item.get("visible") else "INVISIBLE"
                if product.status == "draft":
                    product.status = "imported"
                if product.sync_status == "local_only":
                    product.sync_status = "synced"

            product.primary_image_url = item.get("primary_image", product.primary_image_url)
            product.last_synced_at = func.now()
            count += 1

        await self.db.commit()
        return count

    # ── Archive ───────────────────────────────────────────────

    async def archive_products(self, product_ids: list[uuid.UUID]) -> int:
        """Archive products locally and on Ozon."""
        ozon_ids = []
        local_ids = []
        for pid in product_ids:
            product = await self.get_by_id(pid)
            if product and product.ozon_product_id:
                ozon_ids.append(product.ozon_product_id)
                local_ids.append(pid)
            elif product:
                local_ids.append(pid)

        if ozon_ids and self._endpoints:
            await self.endpoints.archive_products(ozon_ids)

        for pid in local_ids:
            product = await self.get_by_id(pid)
            if product:
                product.status = "archived"
                product.ozon_visibility = "ARCHIVED"

        await self.db.commit()
        return len(local_ids)

    async def delete_product(self, product_id: uuid.UUID) -> bool:
        """Soft-delete a product (set status='deleted'). Also archives on Ozon if pushed.

        Returns True if deleted, False if not found.
        """
        product = await self.get_by_id(product_id)
        if not product:
            return False

        # Archive on Ozon if already pushed
        if product.ozon_product_id and self._endpoints:
            try:
                await self.endpoints.archive_products([product.ozon_product_id])
                product.ozon_visibility = "ARCHIVED"
            except Exception as e:
                logger.warning("Failed to archive on Ozon: %s", e)

        product.status = "deleted"
        self.db.add(product)
        await self.db.commit()
        return True

    async def restore_product(self, product_id: uuid.UUID) -> bool:
        """Restore a soft-deleted product back to draft status.

        Returns True if restored, False if not found.
        """
        product = await self.get_by_id(product_id)
        if not product or product.status != "deleted":
            return False
        product.status = "draft"
        product.sync_status = "local_only"
        self.db.add(product)
        await self.db.commit()
        return True
