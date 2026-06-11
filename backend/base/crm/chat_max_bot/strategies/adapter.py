# Copyright 2025 FARA CRM
# Chat module - MAX message adapter

import mimetypes

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter


class MaxBotMessageAdapter(ChatMessageAdapter):
    """
    Адаптер для парсинга сообщений от MAX (МАКС) Bot API.

    Формат входящего Update (update_type = "message_created"):
    {
        "update_type": "message_created",
        "timestamp": 1690000000000,
        "message": {
            "sender": {
                "user_id": 526725542,
                "first_name": "Артем",
                "last_name": "",
                "name": "Артем",
                "username": "eurodoo",
                "is_bot": false
            },
            "recipient": {
                "chat_id": 123456,
                "chat_type": "dialog",
                "user_id": 526725542
            },
            "timestamp": 1690000000000,
            "body": {
                "mid": "mid.abcdef",
                "seq": 1,
                "text": "привет",
                "attachments": [
                    {"type": "image", "payload": {"url": "https://...", "token": "..."}},
                    {"type": "file", "payload": {"url": "https://...", "token": "...",
                                                  "filename": "doc.pdf", "size": 12345}}
                ]
            }
        },
        "user_locale": "ru"
    }

    Документация: https://dev.max.ru/docs-api
    """

    @property
    def update_type(self) -> str:
        """Тип события (message_created, message_edited, bot_started и т.д.)."""
        return self.raw.get("update_type", "")

    @property
    def _message(self) -> dict:
        """Получить объект message из Update."""
        return self.raw.get("message", {}) or {}

    @property
    def _sender(self) -> dict:
        """Информация об отправителе (User)."""
        return self._message.get("sender", {}) or {}

    @property
    def _recipient(self) -> dict:
        """Информация о получателе/чате (Recipient)."""
        return self._message.get("recipient", {}) or {}

    @property
    def _body(self) -> dict:
        """Тело сообщения (MessageBody)."""
        return self._message.get("body", {}) or {}

    @property
    def _attachments(self) -> list[dict]:
        """Список вложений сообщения."""
        return self._body.get("attachments", []) or []

    @property
    def message_id(self) -> str:
        """ID сообщения в MAX (body.mid)."""
        return str(self._body.get("mid", ""))

    @property
    def chat_id(self) -> str:
        """ID чата в MAX (recipient.chat_id)."""
        return str(self._recipient.get("chat_id", ""))

    @property
    def author_id(self) -> str:
        """ID отправителя в MAX (sender.user_id)."""
        return str(self._sender.get("user_id", ""))

    @property
    def text(self) -> str | None:
        """Текст сообщения."""
        return self._body.get("text")

    @property
    def author_name(self) -> str | None:
        """Имя отправителя."""
        # MAX обычно присылает готовое поле name; иначе собираем из частей.
        name = self._sender.get("name")
        if name:
            return name

        first_name = self._sender.get("first_name", "")
        last_name = self._sender.get("last_name", "")
        username = self._sender.get("username", "")

        name_parts = [p for p in [first_name, last_name] if p]
        full_name = " ".join(name_parts)

        if username and not full_name:
            return f"@{username}"
        elif username:
            return f"{full_name} (@{username})"
        return full_name or None

    @property
    def created_at(self) -> int:
        """Unix timestamp создания сообщения (мс в MAX)."""
        return self._message.get("timestamp") or self.raw.get("timestamp", 0)

    @property
    def images(self) -> list[str]:
        """
        Список URL изображений в сообщении.

        У вложения image payload содержит прямой `url`, поэтому возвращаем
        список URL — базовая стратегия скачает их через file_download.
        """
        urls = []
        for att in self._attachments:
            if att.get("type") != "image":
                continue
            url = (att.get("payload") or {}).get("url")
            if url:
                urls.append(url)
        return urls

    @property
    def files(self) -> list[dict]:
        """
        Список файлов/видео/аудио, у которых есть прямой URL для скачивания.

        Каждый элемент — словарь {url, name, mime_type}. Базовая стратегия
        использует ключ `url`. Вложения без url (например, только с token)
        пропускаем — для них нужен отдельный download-эндпоинт.
        """
        result = []
        for att in self._attachments:
            att_type = att.get("type")
            if att_type not in ("file", "video", "audio"):
                continue
            payload = att.get("payload") or {}
            url = payload.get("url")
            if not url:
                continue
            filename = payload.get("filename") or att_type
            mime_type = (
                mimetypes.guess_type(filename)[0] or "application/octet-stream"
            )
            result.append(
                {
                    "url": url,
                    "name": filename,
                    "mime_type": mime_type,
                    "file_size": payload.get("size", 0),
                }
            )
        return result

    @property
    def should_skip(self) -> bool:
        """
        Определить нужно ли пропустить обработку сообщения.

        Пропускаем:
        - Все события кроме создания сообщения (message_edited, bot_started,
          user_added и прочие сервисные апдейты).
        - Сообщения от ботов (в т.ч. эхо нашего собственного бота).
        - Апдейты без тела сообщения / без mid.
        """
        # Интересует только создание нового сообщения.
        if self.update_type and self.update_type != "message_created":
            return True

        # Сообщения от ботов не обрабатываем.
        if self._sender.get("is_bot", False):
            return True

        # Нет тела сообщения или идентификатора — нечего обрабатывать.
        if not self._body or not self._body.get("mid"):
            return True

        return False

    @property
    def is_from_external(self) -> bool:
        """
        Сообщение от внешнего пользователя (не от нашего бота).

        MAX не шлёт webhook на исходящие сообщения самого бота, поэтому все
        входящие message_created — от пользователей. Дополнительно
        страхуемся флагом is_bot.
        """
        return not self._sender.get("is_bot", False)
