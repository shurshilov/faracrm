# Copyright 2025 FARA CRM
# Chat module - Email message adapter

import re
from email import message_from_bytes
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from email.header import decode_header
from typing import TYPE_CHECKING

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector


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
        """Текст сообщения (предпочтительно plaintext)."""
        if self._is_webhook:
            # Mailgun
            text = self.raw.get("body-plain") or self.raw.get(
                "stripped-text", ""
            )
            # SendGrid
            if not text:
                text = self.raw.get("text", "")
            # Fallback to HTML
            if not text:
                text = self.raw.get("body-html") or self.raw.get("html", "")
            return text or None

        if self._parsed_email:
            return self._get_email_body()

        return None

    @property
    def html(self) -> str | None:
        """HTML версия сообщения."""
        if self._is_webhook:
            return self.raw.get("body-html") or self.raw.get("html")

        if self._parsed_email:
            return self._get_email_body(prefer_html=True)

        return None

    def _get_email_body(self, prefer_html: bool = False) -> str:
        """Извлечь тело письма из email.message.Message."""
        if not self._parsed_email:
            return ""

        msg = self._parsed_email

        if msg.is_multipart():
            text_part = None
            html_part = None

            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Пропускаем вложения
                if "attachment" in content_disposition:
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
    def images(self) -> list[dict]:
        """Список изображений-вложений."""
        return self._get_attachments(filter_type="image")

    @property
    def files(self) -> list[dict]:
        """Список файлов-вложений (не изображения)."""
        return self._get_attachments(filter_type="file")

    def _get_attachments(self, filter_type: str = "all") -> list[dict]:
        """
        Извлечь вложения из письма.

        Args:
            filter_type: "image", "file", или "all"
        """
        attachments = []

        if self._is_webhook:
            # Mailgun/SendGrid вложения обычно в отдельных полях
            # attachment-count, attachment-1, attachment-2, etc.
            attachment_count = int(self.raw.get("attachment-count", 0))
            for i in range(1, attachment_count + 1):
                att = self.raw.get(f"attachment-{i}")
                if att:
                    # Mailgun отдаёт файлы как объекты
                    attachments.append(
                        {
                            "file_name": getattr(
                                att, "filename", f"attachment-{i}"
                            ),
                            "content_type": getattr(
                                att, "content_type", "application/octet-stream"
                            ),
                            "content": (
                                att.read() if hasattr(att, "read") else att
                            ),
                        }
                    )
            return attachments

        if self._parsed_email and self._parsed_email.is_multipart():
            for part in self._parsed_email.walk():
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" not in content_disposition:
                    continue

                filename = part.get_filename()
                if filename:
                    filename = decode_email_header(filename)
                else:
                    filename = "attachment"

                content_type = part.get_content_type()
                payload = part.get_payload(decode=True)

                is_image = content_type.startswith("image/")

                if filter_type == "image" and not is_image:
                    continue
                if filter_type == "file" and is_image:
                    continue

                attachments.append(
                    {
                        "file_name": filename,
                        "content_type": content_type,
                        "content": payload,
                    }
                )

        return attachments

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
    def in_reply_to(self) -> str | None:
        """Message-ID письма на которое это ответ."""
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
