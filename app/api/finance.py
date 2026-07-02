"""Finance routes — transactions, P&L, summary."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, templates
from app.services.finance_service import FinanceService

router = APIRouter(prefix="/finance", tags=["Finance"])


def _svc(db: AsyncSession) -> FinanceService:
    return FinanceService(db)


@router.get("/")
async def finance_list(
    request: Request,
    operation_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    svc = _svc(db)
    items, total = await svc.list_transactions(
        operation_type=operation_type,
        offset=offset,
        limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "finance/list.html",
        {
            "page": "finance",
            "transactions": items,
            "total": total,
            "offset": offset,
            "limit": limit,
        },
    )


@router.get("/pnl/{order_id}")
async def order_pnl(
    order_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    svc = _svc(db)
    pnl = await svc.get_order_pnl(order_id)
    return templates.TemplateResponse(
        request,
        "finance/list.html",
        {"page": "finance", "pnl": pnl},
    )
