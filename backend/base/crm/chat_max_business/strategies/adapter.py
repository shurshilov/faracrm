# Copyright 2025 FARA CRM
# Chat module - MAX (business) message adapter

import re

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter


class MaxBusinessMessageAdapter(ChatMessageAdapter):
    """
    Адаптер входящих сообщений официального API «MAX для бизнеса»
    (platform-api.max.ru). Формат Update тот же, что у Bot API
    (update_type=message_created с message.sender/recipient/body), поэтому
    парсинг повторяет бот-адаптер.

    Отличие бизнес-канала: адресация по НОМЕРУ ТЕЛЕФОНА. Если webhook
    содержит телефон отправителя — ключуем переписку по нему (chat_id =
    телефон), чтобы исходящее «первым» (по номеру) и входящие ответы
    указывали на один external_chat. Если телефона нет — фолбэк на
    recipient.chat_id (как в бот-канале).

    ВНИМАНИЕ: точное место телефона в payload бизнес-вебхука нужно
    подтвердить по официальной доке/кабинету (API гейтован бизнес-
    верификацией, GA Q1 2026) — см. _PHONE_KEYS.
    """

    # Возможные места телефона отправителя в payload (best-effort).
    _PHONE_KEYS = ("phone", "from_phone", "user_phone", "msisdn", "contact")

    @property
    def update_type(self) -> str:
        return self.raw.get("update_type", "")

    @property
    def _message(self) -> dict:
        return self.raw.get("message", {}) or {}

    @property
    def _sender(self) -> dict:
        return self._message.get("sender", {}) or {}

    @property
    def _recipient(self) -> dict:
        return self._message.get("recipient", {}) or {}

    @property
    def _body(self) -> dict:
        return self._message.get("body", {}) or {}

    @property
    def _attachments(self) -> list[dict]:
        return self._body.get("attachments", []) or []

    @staticmethod
    def _digits(value) -> str:
        return re.sub(r"\D", "", str(value or ""))

    @property
    def sender_phone(self) -> str:
        """Телефон отправителя (best-effort) — ищем в sender и в корне."""
        for src in (self._sender, self.raw):
            for key in self._PHONE_KEYS:
                val = src.get(key)
                if val:
                    return self._digits(val)
        return ""

    @property
    def message_id(self) -> str:
        return str(self._body.get("mid", ""))

    @property
    def chat_id(self) -> str:
        """Ключ переписки: телефон (если есть в webhook), иначе chat_id."""
        phone = self.sender_phone
        if phone:
            return phone
        return str(self._recipient.get("chat_id", ""))

    @property
    def author_id(self) -> str:
        phone = self.sender_phone
        if phone:
            return phone
        return str(self._sender.get("user_id", ""))

    @property
    def text(self) -> str | None:
        return self._body.get("text")

    @property
    def author_name(self) -> str | None:
        name = self._sender.get("name")
        if name:
            return name
        first_name = self._sender.get("first_name", "")
        last_name = self._sender.get("last_name", "")
        username = self._sender.get("username", "")
        full_name = " ".join(p for p in [first_name, last_name] if p)
        if username and not full_name:
            return f"@{username}"
        if username:
            return f"{full_name} (@{username})"
        return full_name or None

    @property
    def created_at(self) -> int:
        return self._message.get("timestamp") or self.raw.get("timestamp", 0)

    @property
    def images(self) -> list[str]:
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
        result = []
        for att in self._attachments:
            if att.get("type") not in ("file", "video", "audio"):
                continue
            payload = att.get("payload") or {}
            url = payload.get("url")
            if not url:
                continue
            result.append(
                {
                    "url": url,
                    "name": payload.get("filename") or att.get("type"),
                    "mime_type": "",
                }
            )
        return result

    @property
    def should_skip(self) -> bool:
        # Интересует только создание нового сообщения.
        if self.update_type and self.update_type != "message_created":
            return True
        # Сообщения от ботов/нашего аккаунта не обрабатываем.
        if self._sender.get("is_bot", False):
            return True
        # Нет тела/идентификатора — нечего обрабатывать.
        if not self._body or not self._body.get("mid"):
            return True
        return False

    @property
    def is_from_external(self) -> bool:
        return not self._sender.get("is_bot", False)
