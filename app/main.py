"""FastAPI application entry point — Ozon ERP System."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import engine, async_session_factory
from app.models.base import Base

logger = logging.getLogger(__name__)

# ── Background scheduler for periodic sync ─────────────────────

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def _run_periodic_sync():
    """Run a lightweight periodic sync cycle.

    Executes inside the FastAPI event loop. Each sync is wrapped
    in its own DB session.
    """
    if not settings.is_ozon_configured:
        return

    from app.integrations.client import OzonClient
    from app.services.sync_service import SyncService

    try:
        client = OzonClient()
        async with async_session_factory() as db:
            svc = SyncService(db, client)

            # Sync in priority order (most time-sensitive first)
            await svc.sync_fbs_orders()
            await svc.sync_fbo_orders()
            await svc.sync_products_pull()
            await svc.sync_prices()
            await svc.sync_stocks()

            await db.commit()
            logger.info("Periodic sync completed successfully")
    except Exception:
        logger.exception("Periodic sync failed")
    finally:
        try:
            await client.close()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[arg-type]
    """Startup / shutdown logic."""
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 自动同步已暂停（用户要求）
    # if settings.is_ozon_configured:
    #     scheduler.add_job(
    #         _run_periodic_sync,
    #         trigger="interval",
    #         minutes=settings.SYNC_PRODUCTS_INTERVAL_MINUTES,
    #         id="periodic_sync",
    #         name="Ozon 数据自动同步",
    #         replace_existing=True,
    #     )
    #     scheduler.start()
    #     logger.info("自动同步已启动，间隔 %d 分钟", settings.SYNC_PRODUCTS_INTERVAL_MINUTES)

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# ── Static files ─────────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ── Import and register API router ───────────────────────────────

from app.api.router import router

app.include_router(router)


# ── Health check ──────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.APP_VERSION}


# ── Scheduler status ──────────────────────────────────────────────

@app.get("/api/scheduler/status")
async def scheduler_status():
    """查看自动同步调度器状态。"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return {
        "running": scheduler.running,
        "ozon_configured": settings.is_ozon_configured,
        "sync_interval_minutes": settings.SYNC_PRODUCTS_INTERVAL_MINUTES,
        "jobs": jobs,
    }
