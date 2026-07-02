"""Sync routes — manual trigger, sync history."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_ozon_client, templates
from app.integrations.client import OzonClient
from app.services.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["Sync"])


@router.get("/")
async def sync_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    svc = SyncService(db)
    history = await svc.get_sync_history(limit=50)
    return templates.TemplateResponse(
        request,
        "settings/api.html",
        {
            "page": "settings",
            "sync_history": history,
        },
    )


@router.post("/categories")
async def sync_categories(
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = SyncService(db, ozon_client)
    log = await svc.sync_categories()
    return {"status": log.status, "processed": log.records_processed}


@router.post("/products")
async def sync_products(
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = SyncService(db, ozon_client)
    log = await svc.sync_products_pull()
    return {"status": log.status, "processed": log.records_processed}


@router.post("/prices")
async def sync_prices(
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = SyncService(db, ozon_client)
    log = await svc.sync_prices()
    return {"status": log.status, "processed": log.records_processed}


@router.post("/stocks")
async def sync_stocks(
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = SyncService(db, ozon_client)
    log = await svc.sync_stocks()
    return {"status": log.status, "processed": log.records_processed}


@router.post("/orders/fbs")
async def sync_fbs_orders(
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = SyncService(db, ozon_client)
    log = await svc.sync_fbs_orders()
    return {"status": log.status, "processed": log.records_processed}


@router.post("/orders/fbo")
async def sync_fbo_orders(
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = SyncService(db, ozon_client)
    log = await svc.sync_fbo_orders()
    return {"status": log.status, "processed": log.records_processed}


@router.post("/finance")
async def sync_finance(
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = SyncService(db, ozon_client)
    log = await svc.sync_finance()
    return {"status": log.status, "processed": log.records_processed}


@router.post("/all")
async def full_sync(
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = SyncService(db, ozon_client)
    logs = await svc.full_sync()
    return {
        "status": "completed",
        "results": [
            {"entity": l.entity_type, "status": l.status, "processed": l.records_processed}
            for l in logs
        ],
    }
