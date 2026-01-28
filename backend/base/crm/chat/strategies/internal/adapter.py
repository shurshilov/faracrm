# Copyright 2025 FARA CRM
# Chat module - internal message adapter

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter


class InternalMessageAdapter(ChatMessageAdapter):
    """
    Адаптер для внутренних сообщений FARA CRM.

    Формат сообщения:
    {
        "id": "uuid",
        "chat_id": int,
        "author_id": int,
        "body": "text",
        "created_at": timestamp,
        "attachments": [...]
    }
    """

    @property
    def message_id(self) -> str:
        return str(self.raw.get("id", ""))

    @property
    def chat_id(self) -> str:
        return str(self.raw.get("chat_id", ""))

    @property
    def author_id(self) -> str:
        return str(self.raw.get("author_id", ""))

    @property
    def text(self) -> str | None:
        return self.raw.get("body")

    @property
    def images(self) -> list[str]:
        attachments = self.raw.get("attachments", [])
        return [
            a["url"]
            for a in attachments
            if a.get("type", "").startswith("image/")
        ]

    @property
    def files(self) -> list[dict]:
        attachments = self.raw.get("attachments", [])
        return [
            {
                "url": a["url"],
                "name": a.get("name", "file"),
                "mime_type": a.get("type", "application/octet-stream"),
            }
            for a in attachments
            if not a.get("type", "").startswith("image/")
        ]

    @property
    def created_at(self) -> int:
        return self.raw.get("created_at", 0)

    @property
    def author_name(self) -> str | None:
        return self.raw.get("author_name")

    @property
    def is_from_external(self) -> bool:
        # Для внутреннего чата все сообщения от "внутренних" пользователей
        return False
