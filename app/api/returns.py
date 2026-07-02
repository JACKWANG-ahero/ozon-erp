"""Returns routes — returns list."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, templates

router = APIRouter(prefix="/returns", tags=["Returns"])


@router.get("/")
async def returns_list(
    request: Request,
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func
    from app.models.return_model import Return

    q = select(Return).order_by(Return.return_date.desc())
    count_q = select(func.count(Return.id))
    if status:
        q = q.where(Return.status == status)
        count_q = count_q.where(Return.status == status)
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    items = list(result.scalars().all())
    total = (await db.execute(count_q)).scalar() or 0

    return templates.TemplateResponse(
        request,
        "returns/list.html",
        {
            "page": "returns",
            "returns": items,
            "total": total,
            "offset": offset,
            "limit": limit,
            "status": status,
        },
    )
