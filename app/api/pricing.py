"""Pricing routes — price list, history, bulk update."""

from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_ozon_client, templates
from app.integrations.client import OzonClient
from app.services.price_service import PriceService

router = APIRouter(prefix="/pricing", tags=["Pricing"])


def _svc(db: AsyncSession, client: OzonClient | None = None) -> PriceService:
    return PriceService(db, client)


@router.get("/")
async def price_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "pricing/list.html",
        {"page": "pricing", "prices": [], "total": 0},
    )


@router.get("/history/{product_id}")
async def price_history(
    product_id: UUID,
    request: Request,
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
):
    svc = _svc(db)
    history = await svc.get_price_history(product_id, limit=limit)
    return templates.TemplateResponse(
        request,
        "pricing/list.html",
        {
            "page": "pricing",
            "history": history,
            "product_id": str(product_id),
        },
    )


@router.post("/update")
async def update_price(
    product_id: UUID = Form(...),
    price: float = Form(...),
    old_price: float | None = Form(None),
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    svc = _svc(db, ozon_client)
    result = await svc.update_price(product_id, price, old_price)
    return {"status": "ok", "price": result.price if result else None}
