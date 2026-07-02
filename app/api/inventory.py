"""Inventory routes — stock overview, alerts, warehouse management."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_ozon_client, templates
from app.integrations.client import OzonClient
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _svc(db: AsyncSession, client: OzonClient | None = None) -> InventoryService:
    return InventoryService(db, client)


@router.get("/")
async def inventory_overview(
    request: Request,
    threshold: int = Query(5, ge=0),
    db: AsyncSession = Depends(get_db),
):
    svc = _svc(db)
    warehouses = await svc.get_warehouses()
    low_stock = await svc.get_low_stock_products(threshold=threshold)
    return templates.TemplateResponse(
        request,
        "inventory/overview.html",
        {
            "page": "inventory",
            "warehouses": warehouses,
            "low_stock": low_stock,
            "threshold": threshold,
        },
    )
