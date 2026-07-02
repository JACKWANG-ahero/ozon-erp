"""Chat and ChatMessage models — Ozon customer chat integration."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import (
    DateTime,
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
    from app.models.order import Order


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ozon_chat_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    posting_number: Mapped[str | None] = mapped_column(String(100))
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id"), index=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str | None] = mapped_column(String(30))  # active | closed
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="chat", cascade="all, delete-orphan"
    )
    order: Mapped[Optional["Order"]] = relationship("Order", back_populates="chats")

    def __repr__(self) -> str:
        return f"<Chat id='{self.ozon_chat_id}' status='{self.status}'>"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chats.id"), nullable=False
    )
    ozon_message_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # inbound | outbound
    text: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[dict | None] = mapped_column(JSONB)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage dir='{self.direction}' text='{self.text[:50]}...'>"
