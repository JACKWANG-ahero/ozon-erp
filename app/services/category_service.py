"""Category service — sync Ozon category tree to local DB."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from app.integrations.client import OzonClient
from app.integrations.endpoints.categories import CategoryEndpoints
from app.models.category import Category, CategoryAttribute, AttributeDictionary

logger = logging.getLogger(__name__)


class CategoryService:
    """Manages the local category tree synced from Ozon."""

    def __init__(self, db: AsyncSession, ozon_client: OzonClient | None = None) -> None:
        self.db = db
        self._endpoints: CategoryEndpoints | None = None
        if ozon_client:
            self._endpoints = CategoryEndpoints(ozon_client)

    @property
    def endpoints(self) -> CategoryEndpoints:
        if self._endpoints is None:
            raise RuntimeError("Ozon client not configured")
        return self._endpoints

    # ── Seed categories (fallback when API unavailable) ────────

    SEED_CATEGORIES: list[dict[str, Any]] = [
        {"id": 7000, "parent_id": None, "title_ru": "Одежда / 服装", "children": [
            {"id": 7500, "title_ru": "Женская одежда / 女装", "children": [
                {"id": 17030819, "title_ru": "Платья / 连衣裙"}, {"id": 17031083, "title_ru": "Блузки и рубашки / 衬衫"},
                {"id": 17029521, "title_ru": "Юбки / 裙子"}, {"id": 17029583, "title_ru": "Брюки / 裤子"},
                {"id": 17030535, "title_ru": "Верхняя одежда / 外套"}, {"id": 17029743, "title_ru": "Трикотаж / 针织衫"},
                {"id": 17033445, "title_ru": "Комбинезоны / 连体裤"},
            ]},
            {"id": 7600, "title_ru": "Мужская одежда / 男装", "children": [
                {"id": 17031237, "title_ru": "Футболки / T恤"}, {"id": 17031359, "title_ru": "Рубашки / 衬衫"},
                {"id": 17030923, "title_ru": "Джинсы / 牛仔裤"}, {"id": 17030013, "title_ru": "Брюки / 裤子"},
            ]},
        ]},
        {"id": 8000, "parent_id": None, "title_ru": "Обувь / 鞋类", "children": [
            {"id": 8200, "title_ru": "Женская обувь / 女鞋", "children": [
                {"id": 17031719, "title_ru": "Туфли / 高跟鞋"}, {"id": 17031931, "title_ru": "Кроссовки / 运动鞋"},
                {"id": 17030783, "title_ru": "Ботинки / 靴子"}, {"id": 17029881, "title_ru": "Балетки / 平底鞋"},
            ]},
        ]},
        {"id": 6000, "parent_id": None, "title_ru": "Дом и сад / 家居园艺", "children": [
            {"id": 6200, "title_ru": "Текстиль / 家纺", "children": [
                {"id": 17032251, "title_ru": "Постельное белье / 床上用品"}, {"id": 17032129, "title_ru": "Полотенца / 毛巾"},
                {"id": 17033027, "title_ru": "Шторы / 窗帘"},
            ]},
            {"id": 6400, "title_ru": "Декор / 装饰"},
        ]},
        {"id": 5000, "parent_id": None, "title_ru": "Красота и здоровье / 美妆健康", "children": [
            {"id": 5200, "title_ru": "Уход за лицом / 面部护理"},
            {"id": 5400, "title_ru": "Макияж / 彩妆", "children": [
                {"id": 17029609, "title_ru": "Косметика / 化妆品"}, {"id": 17029775, "title_ru": "Парфюмерия / 香水"},
            ]},
        ]},
        {"id": 4000, "parent_id": None, "title_ru": "Творчество и рукоделие / 手工创意", "children": [
            {"id": 4200, "title_ru": "Вышивание / 刺绣", "children": [
                {"id": 7398, "title_ru": "Наборы для вышивания / 刺绣套装"},
                {"id": 7399, "title_ru": "Мулине и нитки / 绣线"},
                {"id": 7400, "title_ru": "Канва / 绣布"},
                {"id": 7401, "title_ru": "Пяльцы / 绣绷"},
            ]},
            {"id": 4300, "title_ru": "Вязание / 编织"},
            {"id": 4400, "title_ru": "Шитье / 缝纫"},
            {"id": 4500, "title_ru": "Скрапбукинг / 手账"},
            {"id": 4600, "title_ru": "Рисование / 绘画"},
        ]},
        {"id": 3000, "parent_id": None, "title_ru": "Спорт и отдых / 运动休闲", "children": [
            {"id": 17033287, "title_ru": "Спортивная одежда / 运动服"},
            {"id": 17033089, "title_ru": "Обувь для спорта / 运动鞋"},
        ]},
        {"id": 2000, "parent_id": None, "title_ru": "Электроника / 电子产品", "children": [
            {"id": 15502, "title_ru": "Смартфоны / 手机"}, {"id": 15692, "title_ru": "Ноутбуки / 笔记本"},
            {"id": 17033243, "title_ru": "Наушники / 耳机"},
        ]},
        {"id": 17000, "parent_id": None, "title_ru": "Детские товары / 母婴儿童", "children": [
            {"id": 17032731, "title_ru": "Игрушки / 玩具"}, {"id": 17200, "title_ru": "Детская одежда / 童装"},
        ]},
        {"id": 18000, "parent_id": None, "title_ru": "Аксессуары / 配饰", "children": [
            {"id": 17029683, "title_ru": "Часы / 手表"}, {"id": 18200, "title_ru": "Сумки / 包包"},
        ]},
        {"id": 10000, "parent_id": None, "title_ru": "Зоотовары / 宠物用品"},
    ]

    async def seed_categories(self) -> int:
        """Pre-populate with common Ozon categories if table is empty."""
        from sqlalchemy import func as sqlfunc

        result = await self.db.execute(select(sqlfunc.count(Category.id)))
        if (result.scalar() or 0) > 0:
            return 0

        count = 0

        async def walk(nodes: list[dict[str, Any]], parent_id: int | None, level: int) -> None:
            nonlocal count
            for node in nodes:
                children = node.get("children", [])
                self.db.add(Category(
                    id=node["id"], parent_id=parent_id, title_ru=node["title_ru"],
                    level=level, is_leaf=not children,
                ))
                count += 1
                if children:
                    await walk(children, node["id"], level + 1)

        await walk(self.SEED_CATEGORIES, None, 0)
        await self.db.commit()
        logger.info("Seeded %d categories", count)
        return count

    # ── Sync ──────────────────────────────────────────────────

    async def sync_category_tree(self) -> int:
        """Pull category tree from Ozon, falling back to seed data."""
        await self.seed_categories()

        try:
            tree = await self.endpoints.get_tree()
        except Exception as e:
            logger.warning("Ozon category API unavailable, using seed data: %s", e)
            result = await self.db.execute(select(func.count(Category.id)))
            return result.scalar() or 0

        count = 0

        async def walk(nodes: list[dict[str, Any]], parent_id: int | None, level: int) -> None:
            nonlocal count
            for node in nodes:
                cat_id = node.get("category_id", 0)
                title = node.get("title", "")
                type_id = node.get("type_id")  # Ozon product type id
                children = node.get("children", [])
                stmt = insert(Category).values(
                    id=cat_id, parent_id=parent_id, title_ru=title,
                    level=level, is_leaf=not children, type_id=type_id,
                ).on_conflict_do_update(
                    index_elements=["id"],
                    set_={"title_ru": title, "parent_id": parent_id, "level": level,
                           "is_leaf": not children, "type_id": type_id},
                )
                await self.db.execute(stmt)
                count += 1
                if children:
                    await walk(children, cat_id, level + 1)

        await walk(tree, None, 0)
        await self.db.commit()
        logger.info("Synced %d categories from Ozon", count)
        return count

    async def sync_category_attributes(self, description_category_id: int, type_id: int = 0) -> int:
        """Pull attributes for a specific category.

        Returns number of attributes synced.
        """
        attrs = await self.endpoints.get_attributes(description_category_id, type_id)
        count = 0

        for attr in attrs:
            attr_id = attr["id"]
            stmt = insert(CategoryAttribute).values(
                id=attr_id,
                category_id=description_category_id,
                name_ru=attr.get("name", ""),
                type=attr.get("type"),
                is_required=attr.get("is_required", False),
                is_collection=attr.get("is_collection", False),
                dictionary_id=attr.get("dictionary_id"),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name_ru": stmt.excluded.name_ru,
                    "type": stmt.excluded.type,
                    "is_required": stmt.excluded.is_required,
                    "is_collection": stmt.excluded.is_collection,
                    "dictionary_id": stmt.excluded.dictionary_id,
                },
            )
            await self.db.execute(stmt)
            count += 1

            # Sync dictionary values if present
            dict_id = attr.get("dictionary_id")
            if dict_id:
                await self._sync_dictionary(description_category_id, type_id, attr_id, dict_id)

        await self.db.commit()
        return count

    async def _sync_dictionary(
        self, description_category_id: int, type_id: int, attribute_id: int, dictionary_id: int
    ) -> None:
        """Pull dictionary values for an attribute."""
        try:
            values = await self.endpoints.get_attribute_values(
                description_category_id, attribute_id, type_id
            )
            for val in values:
                stmt = insert(AttributeDictionary).values(
                    id=val.get("id", 0),
                    attribute_id=attribute_id,
                    value_ru=val.get("value", ""),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={"value_ru": stmt.excluded.value_ru},
                )
                await self.db.execute(stmt)
        except Exception:
            logger.warning(
                "Failed to sync dictionary for attr %d (dict_id=%d)",
                attribute_id,
                dictionary_id,
                exc_info=True,
            )

    # ── Queries ───────────────────────────────────────────────

    async def get_tree(self) -> list[Category]:
        """Get the full category tree from local DB."""
        result = await self.db.execute(
            select(Category).order_by(Category.level, Category.title_ru)
        )
        return list(result.scalars().all())

    async def get_children(self, parent_id: int | None) -> list[Category]:
        """Get direct children of a category."""
        if parent_id is None:
            result = await self.db.execute(
                select(Category)
                .where(Category.parent_id.is_(None))
                .order_by(Category.title_ru)
            )
        else:
            result = await self.db.execute(
                select(Category)
                .where(Category.parent_id == parent_id)
                .order_by(Category.title_ru)
            )
        return list(result.scalars().all())

    async def get_attributes(self, category_id: int) -> list[CategoryAttribute]:
        """Get attributes for a category from local DB."""
        result = await self.db.execute(
            select(CategoryAttribute).where(
                CategoryAttribute.category_id == category_id
            )
        )
        return list(result.scalars().all())

    async def get_attribute_values(self, attribute_id: int) -> list[AttributeDictionary]:
        """Get dictionary values for an attribute."""
        result = await self.db.execute(
            select(AttributeDictionary).where(
                AttributeDictionary.attribute_id == attribute_id
            )
        )
        return list(result.scalars().all())
