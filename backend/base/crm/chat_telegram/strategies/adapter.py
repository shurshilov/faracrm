# Copyright 2025 FARA CRM
# Chat module - Telegram message adapter

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter


class TelegramMessageAdapter(ChatMessageAdapter):
    """
    Адаптер для парсинга сообщений от Telegram Bot API.

    Формат входящего Update:
    {
        "update_id": 918861950,
        "message": {
            "message_id": 3,
            "from": {
                "id": 526725542,
                "is_bot": false,
                "first_name": "Артем",
                "username": "eurodoo",
                "language_code": "ru"
            },
            "chat": {
                "id": 526725542,
                "first_name": "Артем",
                "username": "eurodoo",
                "type": "private"
            },
            "date": 1750789487,
            "text": "привет"
        }
    }
    """

    @property
    def _message(self) -> dict:
        """Получить объект message из Update."""
        return self.raw.get("message", {})

    @property
    def _from(self) -> dict:
        """Получить информацию об отправителе."""
        return self._message.get("from", {})

    @property
    def _chat(self) -> dict:
        """Получить информацию о чате."""
        return self._message.get("chat", {})

    @property
    def message_id(self) -> str:
        """ID сообщения в Telegram."""
        return str(self._message.get("message_id", ""))

    @property
    def chat_id(self) -> str:
        """ID чата в Telegram."""
        return str(self._chat.get("id", ""))

    @property
    def author_id(self) -> str:
        """ID отправителя в Telegram."""
        return str(self._from.get("id", ""))

    @property
    def text(self) -> str | None:
        """Текст сообщения или caption для медиа."""
        return self._message.get("text") or self._message.get("caption")

    @property
    def author_name(self) -> str | None:
        """Имя отправителя."""
        first_name = self._from.get("first_name", "")
        last_name = self._from.get("last_name", "")
        username = self._from.get("username", "")

        name_parts = [p for p in [first_name, last_name] if p]
        full_name = " ".join(name_parts)

        if username and not full_name:
            return f"@{username}"
        elif username:
            return f"{full_name} (@{username})"
        return full_name or None

    @property
    def created_at(self) -> int:
        """Unix timestamp создания сообщения."""
        return self._message.get("date", 0)

    @property
    def images(self) -> list[dict]:
        """
        Список фотографий в сообщении.

        Telegram присылает несколько размеров для каждой фотографии,
        выбираем с наибольшим размером.
        """
        photos = self._message.get("photo", [])
        if not photos:
            return []

        # Находим фото с наибольшим file_size
        largest = max(photos, key=lambda x: x.get("file_size", 0))
        return [largest]

    @property
    def files(self) -> list[dict]:
        """Список файлов/документов в сообщении."""
        document = self._message.get("document")
        if document:
            return [
                {
                    "file_id": document.get("file_id"),
                    "file_name": document.get("file_name", "document"),
                    "mime_type": document.get(
                        "mime_type", "application/octet-stream"
                    ),
                    "file_size": document.get("file_size", 0),
                }
            ]
        return []

    @property
    def voice(self) -> dict | None:
        """Голосовое сообщение."""
        return self._message.get("voice")

    @property
    def audio(self) -> dict | None:
        """Аудио файл."""
        return self._message.get("audio")

    @property
    def video(self) -> dict | None:
        """Видео файл."""
        return self._message.get("video")

    @property
    def sticker(self) -> dict | None:
        """Стикер."""
        return self._message.get("sticker")

    @property
    def should_skip(self) -> bool:
        """
        Определить нужно ли пропустить обработку сообщения.

        Пропускаем:
        - Сообщения от ботов
        - Служебные сообщения (вход/выход из группы и т.д.)
        """
        # Пропускаем сообщения от ботов
        if self._from.get("is_bot", False):
            return True

        # Пропускаем если нет message (например, edited_message или channel_post)
        if not self._message:
            return True

        # Пропускаем служебные сообщения
        service_fields = [
            "new_chat_members",
            "left_chat_member",
            "new_chat_title",
            "new_chat_photo",
            "delete_chat_photo",
            "group_chat_created",
            "supergroup_chat_created",
            "channel_chat_created",
            "migrate_to_chat_id",
            "migrate_from_chat_id",
            "pinned_message",
        ]

        for field in service_fields:
            if field in self._message:
                return True

        return False

    @property
    def is_from_external(self) -> bool:
        """
        Сообщение от внешнего пользователя (не от бота).

        В Telegram все входящие webhook сообщения - от пользователей,
        бот сам не шлёт webhook'и на свои сообщения.
        """
        return not self._from.get("is_bot", False)
