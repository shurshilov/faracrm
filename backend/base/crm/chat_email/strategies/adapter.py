# Copyright 2025 FARA CRM
# Chat module - Email message adapter

import json
import mimetypes
import re
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from email.header import decode_header
from typing import TYPE_CHECKING

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter
from backend.base.crm.chat_email.sanitizer import sanitize_email_html

if TYPE_CHECKING:
    from backend.project_setup import ChatConnector


def decode_email_header(header_value: str | None) -> str:
    """Декодировать заголовок email (может быть в разных кодировках)."""
    if not header_value:
        return ""

    decoded_parts = []
    for part, charset in decode_header(header_value):
        if isinstance(part, bytes):
            decoded_parts.append(
                part.decode(charset or "utf-8", errors="replace")
            )
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


class EmailMessageAdapter(ChatMessageAdapter):
    """
    Адаптер для парсинга email сообщений.

    Поддерживает:
    - IMAP fetched messages (raw bytes)
    - Inbound webhook от Mailgun/SendGrid (parsed dict)

    Формат для IMAP:
    {
        "uid": 123,
        "raw": b"...",  # RFC822 bytes
        "parsed": email.message.Message object
    }

    Формат для Mailgun webhook:
    {
        "sender": "user@example.com",
        "recipient": "support@company.com",
        "subject": "Hello",
        "body-plain": "Plain text",
        "body-html": "<html>...",
        "Message-Id": "<...@example.com>",
        "timestamp": "1234567890"
    }

    Формат для SendGrid Inbound Parse:
    {
        "from": "user@example.com",
        "to": "support@company.com",
        "subject": "Hello",
        "text": "Plain text",
        "html": "<html>...",
        "headers": "..."
    }
    """

    def __init__(self, connector: "ChatConnector", raw: dict):
        """
        Args:
            connector: Экземпляр коннектора
            raw: Сырые данные сообщения от провайдера
        """
        self.connector = connector
        self._raw_data = raw

    @property
    def raw(self) -> dict:
        """
        Возвращает raw данные в JSON-совместимом формате.
        Исключает bytes и Message объекты которые нельзя сериализовать.
        """
        if self._is_webhook:
            return self._raw_data

        # Для IMAP - возвращаем только сериализуемые данные
        return {
            "uid": self._raw_data.get("uid"),
            "source": "imap",
        }

    @property
    def _parsed_email(self) -> Message | None:
        """Получить распарсенный email объект."""
        return self._raw_data.get("parsed")

    @property
    def _is_webhook(self) -> bool:
        """Проверить является ли это webhook от Mailgun/SendGrid."""
        # Если есть "parsed" - это IMAP, иначе webhook
        return "parsed" not in self._raw_data

    @property
    def message_id(self) -> str:
        """Message-ID email сообщения."""
        if self._is_webhook:
            # Mailgun
            msg_id = self.raw.get("Message-Id") or self.raw.get(
                "message-id", ""
            )
            # SendGrid - извлекаем из headers
            if not msg_id:
                headers = self.raw.get("headers", "")
                match = re.search(
                    r"Message-ID:\s*(<[^>]+>)", headers, re.IGNORECASE
                )
                if match:
                    msg_id = match.group(1)
            return msg_id

        if self._parsed_email:
            return self._parsed_email.get("Message-ID", "") or ""

        return str(self.raw.get("uid", ""))

    @property
    def chat_id(self) -> str:
        """
        Email адрес отправителя как chat_id.
        Для email чат = переписка с конкретным адресом.
        """
        return self.author_id

    @property
    def author_id(self) -> str:
        """Email адрес отправителя."""
        if self._is_webhook:
            # Mailgun
            sender = self.raw.get("sender") or self.raw.get("from", "")
            # SendGrid
            if not sender:
                sender = self.raw.get("from", "")
            name, email_addr = parseaddr(sender)
            return email_addr.lower()

        if self._parsed_email:
            from_header = self._parsed_email.get("From", "")
            name, email_addr = parseaddr(from_header)
            return email_addr.lower()

        return ""

    @property
    def text(self) -> str | None:
        """Текст сообщения (предпочтительно plaintext, всегда санитизируется)."""
        if self._is_webhook:
            text = (
                self.raw.get("body-plain")
                or self.raw.get("stripped-text")
                or self.raw.get("text")
                or self.raw.get("body-html")
                or self.raw.get("html")
                or ""
            )
        elif self._parsed_email:
            text = self._get_email_body()
        else:
            return None

        return sanitize_email_html(text) if text else None

    @property
    def html(self) -> str | None:
        """HTML версия сообщения (санитизированная)."""
        if self._is_webhook:
            raw_html = self.raw.get("body-html") or self.raw.get("html")
        elif self._parsed_email:
            raw_html = self._get_email_body(prefer_html=True)
        else:
            return None

        return sanitize_email_html(raw_html) if raw_html else None

    @property
    def serialized_body(self) -> str:
        """
        Тело для хранения в chat_message — «email-формат» {subject, html}
        (по аналогии с system-сообщением, хранящим JSON {event, params}).
        Так тема письма едет внутри body и парсится email-кодом, без
        отдельного поля/параметра. Переопределяет ChatMessageAdapter.
        Обратная операция — parse_email_body в strategy.py.
        """
        return json.dumps(
            {
                "subject": self.subject or "",
                "html": self.html or self.text or "",
            }
        )

    def _get_email_body(self, prefer_html: bool = False) -> str:
        """Извлечь тело письма из email.message.Message."""
        if not self._parsed_email:
            return ""

        msg = self._parsed_email

        if msg.is_multipart():
            text_part = None
            html_part = None

            for index, part in enumerate(msg.walk(), 1):
                content_type = part.get_content_type()

                # Пропускаем вложения — тем же правилом, каким их забирает
                # attachments, чтобы часть не попала и туда, и сюда.
                if self._attachment_name(part, index):
                    continue

                if content_type == "text/plain" and not text_part:
                    text_part = part
                elif content_type == "text/html" and not html_part:
                    html_part = part

            if prefer_html and html_part:
                return self._decode_part(html_part)
            if text_part:
                return self._decode_part(text_part)
            if html_part:
                return self._decode_part(html_part)
            return ""
        else:
            # Письмо из одного файла (Content-Type: application/pdf) — это
            # вложение, а не тело: иначе байты декодируются в абракадабру.
            if self._attachment_name(msg, 1):
                return ""
            return self._decode_part(msg)

    def _decode_part(self, part: Message) -> str:
        """Декодировать часть письма."""
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
        return str(payload) if payload else ""

    @property
    def author_name(self) -> str | None:
        """Имя отправителя."""
        if self._is_webhook:
            sender = self.raw.get("sender") or self.raw.get("from", "")
            name, email_addr = parseaddr(sender)
            return name if name else email_addr

        if self._parsed_email:
            from_header = self._parsed_email.get("From", "")
            decoded = decode_email_header(from_header)
            name, email_addr = parseaddr(decoded)
            return name if name else email_addr

        return None

    @property
    def subject(self) -> str | None:
        """Тема письма."""
        if self._is_webhook:
            return self.raw.get("subject")

        if self._parsed_email:
            subj = self._parsed_email.get("Subject", "")
            return decode_email_header(subj)

        return None

    @property
    def created_at(self) -> int:
        """Unix timestamp создания сообщения."""
        if self._is_webhook:
            # Mailgun timestamp
            ts = self.raw.get("timestamp")
            if ts:
                return int(ts)
            return 0

        if self._parsed_email:
            date_header = self._parsed_email.get("Date", "")
            try:
                dt = parsedate_to_datetime(date_header)
                return int(dt.timestamp())
            except Exception:
                return 0

        return 0

    @property
    def files(self) -> list[dict]:
        """
        Вложения письма С СОДЕРЖИМЫМ: [{name, mime_type, content}].

        Всё одним списком: делить на images/files незачем, общий приёмник
        всё равно их склеивает (стратегия объявляет attachments_source =
        "content", поэтому скачивание не вызывается).
        """
        if self._is_webhook:
            # Mailgun/SendGrid: attachment-count, attachment-1, attachment-2...
            count = int(self.raw.get("attachment-count", 0))
            files = []
            for i in range(1, count + 1):
                att = self.raw.get(f"attachment-{i}")
                if att:
                    files.append(
                        {
                            "name": getattr(
                                att, "filename", f"attachment-{i}"
                            ),
                            "mime_type": getattr(att, "content_type", None),
                            "content": (
                                att.read() if hasattr(att, "read") else att
                            ),
                        }
                    )
            return files

        if not self._parsed_email:
            return []

        files = []
        # Без is_multipart(): письмо может целиком состоять из одного файла.
        for index, part in enumerate(self._parsed_email.walk(), 1):
            name = self._attachment_name(part, index)
            payload = part.get_payload(decode=True) if name else None
            if payload:
                files.append(
                    {
                        "name": name,
                        "mime_type": part.get_content_type(),
                        "content": payload,
                    }
                )
        return files

    @staticmethod
    def _attachment_name(part: Message, index: int) -> str | None:
        """Имя файла, если часть — вложение. Иначе None (это тело письма)."""
        if part.get_content_maintype() == "multipart":
            return None

        disposition = str(part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()
        # Текстовая часть с именем, но без disposition — это тело письма
        # (у него тоже бывает параметр name), а не файл.
        if filename and (
            "attachment" in disposition
            or part.get_content_maintype() != "text"
        ):
            return decode_email_header(filename)
        if "attachment" in disposition:
            return "attachment"

        # Картинка, вставленная в тело: имени нет, есть только Content-ID.
        # Без своего имени она пропадала бесследно — src="cid:..." вырезает
        # санитайзер, а вложением она не считалась.
        content_id = (part.get("Content-ID") or "").strip("<> ")
        if content_id and part.get_content_maintype() != "text":
            ext = mimetypes.guess_extension(part.get_content_type()) or ""
            return f"inline-{index}{ext}"

        return None

    @property
    def should_skip(self) -> bool:
        """
        Определить нужно ли пропустить обработку сообщения.

        Пропускаем:
        - Auto-reply сообщения
        - Bounce сообщения
        - Сообщения без отправителя
        """
        if not self.author_id:
            return True

        # Проверяем auto-reply заголовки
        if self._parsed_email:
            auto_submitted = self._parsed_email.get("Auto-Submitted", "")
            if auto_submitted and auto_submitted.lower() != "no":
                return True

            # Проверяем precedence (bulk, junk, list)
            precedence = self._parsed_email.get("Precedence", "")
            if precedence.lower() in ("bulk", "junk", "list"):
                return True

            # Проверяем X-Auto-Response-Suppress
            if self._parsed_email.get("X-Auto-Response-Suppress"):
                return True

        return False

    @property
    def is_from_external(self) -> bool:
        """
        Сообщение от внешнего пользователя.
        Для email все входящие сообщения считаются внешними.
        """
        return True

    @property
    def reply_to(self) -> str | None:
        """Адрес для ответа."""
        if self._parsed_email:
            reply_to = self._parsed_email.get("Reply-To", "")
            if reply_to:
                name, email_addr = parseaddr(reply_to)
                return email_addr
        return None

    @property
    def thread_message_ids(self) -> list[str]:
        """
        ID писем этой переписки, которые несёт входящее (см. базовый адаптер).

        Собирается из двух заголовков: References — вся цепочка, In-Reply-To —
        письмо, на которое отвечают напрямую. Берём оба и объединяем: клиент
        или релей может срезать один из них, и тогда сработает второй.

        Порядок неважен — ищем по совпадению с ЛЮБЫМ из них.
        """
        ids = list(self.references)
        parent = self.in_reply_to
        if parent and parent not in ids:
            ids.append(parent)
        return ids

    @property
    def in_reply_to(self) -> str | None:
        """Message-ID письма на которое это ответ (заголовок In-Reply-To)."""
        if self._is_webhook:
            return self.raw.get("In-Reply-To")

        if self._parsed_email:
            return self._parsed_email.get("In-Reply-To")

        return None

    @property
    def references(self) -> list[str]:
        """Список Message-ID из цепочки переписки."""
        refs_str = ""

        if self._is_webhook:
            refs_str = self.raw.get("References", "")
        elif self._parsed_email:
            refs_str = self._parsed_email.get("References", "") or ""

        if refs_str:
            # References это строка с Message-ID разделёнными пробелами/переносами
            return re.findall(r"<[^>]+>", refs_str)

        return []
