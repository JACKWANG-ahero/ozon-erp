"""Dashboard routes — main page and KPI data."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, templates
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["Dashboard"])


@router.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Main dashboard page."""
    svc = AnalyticsService(db)
    kpis = await svc.get_dashboard_kpis()
    trend = await svc.get_sales_trend(days=30)
    top = await svc.get_top_products(limit=10)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "page": "dashboard",
            "kpis": kpis,
            "trend": trend,
            "top_products": top,
        },
    )


@router.get("/api/dashboard/kpis")
async def dashboard_kpis(db: AsyncSession = Depends(get_db)):
    """JSON endpoint for dashboard KPIs."""
    svc = AnalyticsService(db)
    return await svc.get_dashboard_kpis()
