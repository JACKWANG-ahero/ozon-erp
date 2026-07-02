"""Application configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings for the Ozon ERP application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    APP_NAME: str = "Ozon ERP"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./ozon_erp.db"

    # ── Ozon Seller API ──────────────────────────────────────
    OZON_CLIENT_ID: str = ""
    OZON_API_KEY: str = ""
    OZON_BASE_URL: str = "https://api-seller.ozon.ru"

    # ── Rate Limiter ─────────────────────────────────────────
    OZON_RATE_LIMIT_PER_MINUTE: int = 80
    OZON_BATCH_DELAY_SECONDS: float = 0.6

    # ── DeepSeek Translation ─────────────────────────────────
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/anthropic"

    # ── Doubao (豆包) Multimodal Translation ─────────────────
    DOUBAO_API_KEY: str = ""
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL: str = "doubao-seed-1-8-251228"

    # ── GitHub CDN (图片公网访问) ──────────────────────────
    GITHUB_TOKEN: str = ""
    GITHUB_OWNER: str = ""

    # ── Sourcing ────────────────────────────────────────────
    OZON_EMBROIDERY_CATEGORY_ID: int = 0  # 刺绣套装类目ID，上线前配置

    # ── Sync ─────────────────────────────────────────────────
    SYNC_PRODUCTS_INTERVAL_MINUTES: int = 15
    SYNC_PRICES_INTERVAL_MINUTES: int = 5
    SYNC_STOCKS_INTERVAL_MINUTES: int = 5
    SYNC_FBS_ORDERS_INTERVAL_MINUTES: int = 2
    SYNC_FBO_ORDERS_INTERVAL_MINUTES: int = 15
    SYNC_FINANCE_INTERVAL_MINUTES: int = 30
    SYNC_CATEGORIES_INTERVAL_HOURS: int = 24

    # ── Paths ────────────────────────────────────────────────
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    @property
    def is_ozon_configured(self) -> bool:
        return bool(self.OZON_CLIENT_ID and self.OZON_API_KEY)


settings = Settings()
