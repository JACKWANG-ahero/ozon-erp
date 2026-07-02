"""Ozon Chat API endpoint wrappers.

Covers:
- POST /v1/chat/list
- POST /v1/chat/send
- POST /v1/chat/send/file
- POST /v1/chat/create
- POST /v1/chat/history
- POST /v1/chat/read
"""

from __future__ import annotations

from typing import Any

from app.integrations.client import OzonClient


class ChatEndpoints:
    """Wraps /v1/chat/* endpoints."""

    def __init__(self, client: OzonClient) -> None:
        self.client = client

    async def list_chats(
        self, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """POST /v1/chat/list."""
        return await self.client.post(
            "/v1/chat/list",
            {"limit": limit, "offset": offset},
        )

    async def send_message(
        self, chat_id: str, text: str, attachments: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """POST /v1/chat/send."""
        body: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if attachments:
            body["attachments"] = attachments
        return await self.client.post("/v1/chat/send", body)

    async def send_file(
        self, chat_id: str, file_url: str, file_name: str = ""
    ) -> dict[str, Any]:
        """POST /v1/chat/send/file — Send a file to a chat."""
        body: dict[str, Any] = {"chat_id": chat_id, "file_url": file_url}
        if file_name:
            body["file_name"] = file_name
        return await self.client.post("/v1/chat/send/file", body)

    async def create_chat(
        self, posting_number: str, text: str = ""
    ) -> dict[str, Any]:
        """POST /v1/chat/create — Start a new chat with a buyer.

        ``posting_number`` — Order/posting number to associate with the chat.
        """
        body: dict[str, Any] = {"posting_number": posting_number}
        if text:
            body["text"] = text
        return await self.client.post("/v1/chat/create", body)

    async def get_history(
        self, chat_id: str, limit: int = 100, from_message_id: str | None = None
    ) -> dict[str, Any]:
        """POST /v1/chat/history — Get chat message history.

        Returns messages in reverse chronological order (newest first).
        """
        body: dict[str, Any] = {"chat_id": chat_id, "limit": limit}
        if from_message_id:
            body["from_message_id"] = from_message_id
        return await self.client.post("/v1/chat/history", body)

    async def mark_read(self, chat_id: str, message_ids: list[str]) -> dict[str, Any]:
        """POST /v1/chat/read — Mark messages as read."""
        return await self.client.post(
            "/v1/chat/read",
            {"chat_id": chat_id, "message_ids": message_ids},
        )
