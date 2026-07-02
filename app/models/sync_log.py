"""SyncLog model — audit trail for all Ozon ↔ local synchronization operations."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy import JSON as JSONB
from sqlalchemy import Uuid as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # product | stock | price | order | finance | category | returns | chat
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    # pull | push

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    # running | success | partial | failed

    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    request_body: Mapped[dict | None] = mapped_column(JSONB)
    response_body: Mapped[dict | None] = mapped_column(JSONB)

    def __repr__(self) -> str:
        return (
            f"<SyncLog entity='{self.entity_type}' dir='{self.direction}' "
            f"status='{self.status}'>"
        )
