"""Category routes — tree browser, JSON API, and classification."""

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_ozon_client, templates
from app.integrations.client import OzonClient
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/")
async def category_tree_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Category tree browser page."""
    svc = CategoryService(db)
    categories = await svc.get_tree()
    return templates.TemplateResponse(
        request,
        "categories/list.html",
        {"page": "categories", "categories": categories},
    )


# ── JSON API for tree picker ──────────────────────────────────


@router.get("/api/classify")
async def category_classify_json(
    name: str = Query(...),
    description: str = Query(""),
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    """Return category suggestions as JSON for autocomplete.

    Calls Ozon /v1/product/classify and returns simplified results:
        [{"category_id": 17028922, "title": "..."}, ...]
    Falls back to local category search if Ozon is unavailable.
    """
    results: list[dict] = []

    # Try Ozon classify API first
    if ozon_client:
        try:
            from app.integrations.endpoints.products import ProductEndpoints
            ep = ProductEndpoints(ozon_client)
            ozon_results = await ep.classify_product(name, description or None)
            for r in ozon_results[:20]:
                results.append({
                    "category_id": r.get("category_id", 0),
                    "title": r.get("title", r.get("category_name", "")),
                })
            return results
        except Exception:
            pass  # fallback to local search

    # Fallback: local DB search by title
    from app.services.category_service import CategoryService
    svc = CategoryService(db)
    await svc.seed_categories()
    all_cats = await svc.get_tree()
    q = name.lower()
    for c in all_cats:
        title = (c.title_ru or "").lower()
        title_zh = (c.title_zh or "").lower()
        if q in title or q in title_zh:
            results.append({
                "category_id": c.id,
                "title": c.title_ru + (f" / {c.title_zh}" if c.title_zh else ""),
            })
            if len(results) >= 20:
                break
    return results


@router.get("/api/tree")
async def category_tree_json(
    db: AsyncSession = Depends(get_db),
):
    """Return category tree as JSON for frontend picker.

    Response format::
        [
          {"id": 7000, "title": "Одежда / 服装", "children": [...]},
          ...
        ]
    """
    svc = CategoryService(db)
    # Auto-seed if empty
    await svc.seed_categories()
    all_cats = await svc.get_tree()

    # Build nested tree
    by_parent: dict[int | None, list[dict]] = {}
    for c in all_cats:
        by_parent.setdefault(c.parent_id, []).append({
            "id": c.id,
            "title": c.title_ru,
            "level": c.level,
            "is_leaf": c.is_leaf,
        })

    def build_tree(parent_id: int | None) -> list[dict]:
        children = by_parent.get(parent_id, [])
        for child in children:
            grandkids = build_tree(child["id"])
            if grandkids:
                child["children"] = grandkids
        return children

    return build_tree(None)


@router.get("/classify")
async def classify_form(request: Request):
    """Product category auto-classification form."""
    return templates.TemplateResponse(
        request,
        "products/form.html",
        {"page": "categories", "product": None, "classify_mode": True},
    )


@router.post("/classify")
async def classify_product(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return templates.TemplateResponse(
            request,
            "products/form.html",
            {"page": "categories", "error": "Ozon API 未配置", "classify_mode": True},
        )

    from app.integrations.endpoints.products import ProductEndpoints
    endpoints = ProductEndpoints(ozon_client)
    try:
        results = await endpoints.classify_product(name, description or None)
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "products/form.html",
            {"page": "categories", "error": f"分类查询失败：{e}", "classify_mode": True},
        )

    return templates.TemplateResponse(
        request,
        "products/form.html",
        {
            "page": "categories",
            "classify_results": results,
            "classify_name": name,
            "classify_mode": True,
        },
    )


@router.get("/lookup")
async def category_lookup(request: Request):
    """Category ID lookup helper page."""
    return templates.TemplateResponse(
        request,
        "products/form.html",
        {"page": "categories", "classify_mode": True, "lookup_mode": True},
    )
