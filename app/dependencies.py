"""FastAPI dependencies (get_db, get_ozon_client, templates, etc.)."""

from typing import AsyncGenerator

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.integrations.client import OzonClient


# ── Database ──────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, commit on success, rollback on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Ozon API Client ───────────────────────────────────────────────


def get_ozon_client() -> OzonClient | None:
    """Return an OzonClient instance if credentials are configured.

    Returns ``None`` when OZON_CLIENT_ID / OZON_API_KEY are not set so
    the UI can still render without API access (settings page will prompt).
    """
    if not settings.is_ozon_configured:
        return None
    return OzonClient()


# ── Jinja2 Templates ──────────────────────────────────────────────

templates = Jinja2Templates(
    directory=str(settings.BASE_DIR / "app" / "templates"),
)


def flash(request: Request, message: str, category: str = "info") -> None:
    """Add a flash message to the session."""
    session = request.session
    if "_flashes" not in session:
        session["_flashes"] = []
    session["_flashes"].append({"message": message, "category": category})


def get_flashes(request: Request) -> list[dict[str, str]]:
    """Pop and return all flash messages."""
    session = request.session
    flashes: list[dict[str, str]] = session.pop("_flashes", [])
    return flashes
