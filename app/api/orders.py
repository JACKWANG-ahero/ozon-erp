"""Order routes — FBS/FBO order list, detail, status transitions."""

from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_ozon_client, templates
from app.integrations.client import OzonClient
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])


def _svc(db: AsyncSession, client: OzonClient | None = None) -> OrderService:
    return OrderService(db, client)


@router.get("/")
async def order_list(
    request: Request,
    order_type: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = _svc(db)
    items, total = await svc.list_orders(
        order_type=order_type, status=status,
        offset=offset, limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "orders/list.html",
        {
            "page": "orders",
            "orders": items,
            "total": total,
            "offset": offset,
            "limit": limit,
            "filter_type": order_type,
            "filter_status": status,
        },
    )


@router.get("/{order_id}")
async def order_detail(
    request: Request,
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = _svc(db)
    order = await svc.get_order_detail(order_id)
    if not order:
        return templates.TemplateResponse(
            request,
            "base.html",
            {"page": "orders", "error": "Order not found"},
            status_code=404,
        )
    history = await svc.get_order_status_history(order_id)
    return templates.TemplateResponse(
        request,
        "orders/detail.html",
        {
            "page": "orders",
            "order": order,
            "status_history": history,
        },
    )


# ── FBS Workflow Actions ─────────────────────────────────────────


@router.post("/{order_id}/ship")
async def order_ship(
    order_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = _svc(db, ozon_client)
    result = await svc.ship_order(order_id)
    return {"status": "ok", "result": result}


@router.post("/{order_id}/tracking")
async def order_set_tracking(
    order_id: UUID,
    tracking_number: str = Form(...),
    carrier: str = Form(""),
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = _svc(db, ozon_client)
    result = await svc.set_tracking(order_id, tracking_number, carrier)
    return {"status": "ok", "result": result}


@router.post("/{order_id}/delivering")
async def order_delivering(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = _svc(db, ozon_client)
    result = await svc.mark_delivering(order_id)
    return {"status": "ok", "result": result}


@router.post("/{order_id}/delivered")
async def order_delivered(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        return {"error": "Ozon API not configured"}
    svc = _svc(db, ozon_client)
    result = await svc.mark_delivered(order_id)
    return {"status": "ok", "result": result}
