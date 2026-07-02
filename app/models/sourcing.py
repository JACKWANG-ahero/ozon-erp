"""1688 Sourcing record model — stores scraped data, translations, and push status."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import JSON as JSONB
from sqlalchemy import Uuid as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.sourcing import SourcingSku


class SourcingRecord(Base):
    """A product sourced from 1688, tracked through translation → push."""

    __tablename__ = "sourcing_records"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Source ──────────────────────────────────────────────
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    article_number: Mapped[str | None] = mapped_column(String(100))

    # ── Chinese original ────────────────────────────────────
    title_cn: Mapped[str] = mapped_column(String(500), nullable=False)
    material_cn: Mapped[str | None] = mapped_column(Text)
    package_type_cn: Mapped[str | None] = mapped_column(String(500))
    description_cn: Mapped[str | None] = mapped_column(Text)

    # ── Russian translation ─────────────────────────────────
    title_ru: Mapped[str | None] = mapped_column(String(500))
    description_ru: Mapped[str | None] = mapped_column(Text)
    material_ru: Mapped[str | None] = mapped_column(Text)
    package_type_ru: Mapped[str | None] = mapped_column(String(500))

    # ── Raw scraped data (full JSON from browser) ───────────
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    # ── Package / logistics ─────────────────────────────────
    weight_kg: Mapped[float | None] = mapped_column(Float)
    length_cm: Mapped[float | None] = mapped_column(Float)
    width_cm: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)

    # ── Images ──────────────────────────────────────────────
    images_1688_urls: Mapped[list | None] = mapped_column(JSONB)
    detail_images_1688_urls: Mapped[list | None] = mapped_column(JSONB)
    images_local_paths: Mapped[list | None] = mapped_column(JSONB)
    images_ozon_urls: Mapped[list | None] = mapped_column(JSONB)

    # ── OZON push status ────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(30),
        default="draft",
        # draft → translated → cost_calculated → ready_to_push
        # → pushed → push_failed → live
    )
    ozon_offer_id: Mapped[str | None] = mapped_column(String(255))
    ozon_product_id: Mapped[int | None] = mapped_column(Integer)
    ozon_category_id: Mapped[int | None] = mapped_column(Integer)

    push_errors: Mapped[dict | None] = mapped_column(JSONB)

    # ── Costing ─────────────────────────────────────────────
    cost_data: Mapped[dict | None] = mapped_column(JSONB)

    # ── Timestamps ──────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    skus: Mapped[List["SourcingSku"]] = relationship(
        "SourcingSku", back_populates="record", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SourcingRecord title='{self.title_cn[:40]}' status='{self.status}'>"


class SourcingSku(Base):
    """Individual SKU variant for a sourced product."""

    __tablename__ = "sourcing_skus"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sourcing_records.id"),
        nullable=False,
    )

    spec_cn: Mapped[str] = mapped_column(String(500), nullable=False)
    spec_ru: Mapped[str | None] = mapped_column(String(500))
    price_cny: Mapped[float | None] = mapped_column(Float)
    moq: Mapped[int | None] = mapped_column(Integer)
    stock: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    record: Mapped["SourcingRecord"] = relationship("SourcingRecord", back_populates="skus")

    def __repr__(self) -> str:
        return f"<SourcingSku spec='{self.spec_cn[:30]}' price={self.price_cny}>"
