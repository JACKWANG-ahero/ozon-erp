"""Ozon Category API endpoint wrappers."""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.client import OzonClient

logger = logging.getLogger(__name__)

# ── Cache (in-memory TTLCache) ────────────────────────────────────
# Simple dict cache; replace with Redis for production.
_category_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 3600  # 1 hour


def _cache_get(key: str) -> Any | None:
    import time

    entry = _category_cache.get(key)
    if entry:
        ts, val = entry
        if time.monotonic() - ts < _CACHE_TTL:
            return val
        del _category_cache[key]
    return None


def _cache_set(key: str, value: Any) -> None:
    import time

    _category_cache[key] = (time.monotonic(), value)


class CategoryEndpoints:
    """Wraps /v1/category/* endpoints."""

    def __init__(self, client: OzonClient) -> None:
        self.client = client

    async def get_tree(self) -> list[dict[str, Any]]:
        """POST /v1/description-category/tree — Full category tree.

        Returns a list of top-level category objects, each with a
        ``children`` list.
        """
        cached = _cache_get("category_tree")
        if cached:
            return cached

        result = await self.client.post(
            "/v1/description-category/tree", {"language": "DEFAULT"}
        )
        tree: list[dict[str, Any]] = result.get("result", [])
        _cache_set("category_tree", tree)
        return tree

    async def get_attributes(
        self,
        description_category_id: int,
        type_id: int = 0,
        language: str = "DEFAULT",
    ) -> list[dict[str, Any]]:
        """POST /v1/description-category/attribute — Attributes for a category.

        Returns list of attribute definitions::
            [{"id": 8229, "name": "...", "type": "...", "is_required": true, ...}, ...]
        """
        cache_key = f"cat_attrs_{description_category_id}_{type_id}_{language}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        result = await self.client.post(
            "/v1/description-category/attribute",
            {
                "description_category_id": description_category_id,
                "type_id": type_id,
                "language": language,
            },
        )
        attrs: list[dict[str, Any]] = result.get("result", [])
        _cache_set(cache_key, attrs)
        return attrs

    async def get_attribute_values(
        self,
        description_category_id: int,
        attribute_id: int,
        type_id: int = 0,
        language: str = "DEFAULT",
        last_value_id: int = 0,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        """POST /v1/description-category/attribute/values — Dictionary values for an attribute.

        Returns::
            [{"id": 123, "value": "..."}, ...]
        """
        cache_key = f"cat_attr_vals_{description_category_id}_{attribute_id}_{type_id}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        result = await self.client.post(
            "/v1/description-category/attribute/values",
            {
                "description_category_id": description_category_id,
                "attribute_id": attribute_id,
                "type_id": type_id,
                "language": language,
                "last_value_id": last_value_id,
                "limit": limit,
            },
        )
        values: list[dict[str, Any]] = result.get("result", [])
        _cache_set(cache_key, values)
        return values

    async def search_attribute_values(
        self,
        attribute_id: int,
        description_category_id: int,
        type_id: int,
        value: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """POST /v1/description-category/attribute/values/search — Search attribute values.

        Searches for reference values matching ``value`` (minimum 2 characters).
        Not cached — search queries vary per user input.

        Returns::
            [{"id": 123, "value": "...", "info": "...", "picture": "..."}, ...]
        """
        result = await self.client.post(
            "/v1/description-category/attribute/values/search",
            {
                "attribute_id": attribute_id,
                "description_category_id": description_category_id,
                "type_id": type_id,
                "value": value,
                "limit": limit,
            },
        )
        return result.get("result", [])
