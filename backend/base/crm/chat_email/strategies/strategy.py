# Copyright 2025 FARA CRM
# Chat module - Email strategy (SMTP/IMAP)

import logging
import re
import uuid
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders, message_from_bytes
from email.utils import formataddr
from typing import TYPE_CHECKING, Any, Tuple

import aiosmtplib
import aioimaplib

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
from .adapter import EmailMessageAdapter


if TYPE_CHECKING:
    from backend.project_setup import ChatConnector
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)


class EmailStrategy(ChatStrategyBase):
    """
    Стратегия для интеграции с Email через SMTP/IMAP.

    Поддерживает:
    - Отправку сообщений через SMTP (aiosmtplib)
    - Получение сообщений через IMAP polling (aioimaplib)
    - Вложения (attachments)
    - HTML и plaintext

    Поля коннектора (добавляются через mixin):
    - smtp_host, smtp_port, smtp_encryption
    - imap_host, imap_port, imap_ssl
    - email_username, email_password
    - email_from, email_from_name, email_reply_to, email_bounce
    - email_default_subject
    - imap_last_uid
    """

    strategy_type = "email"
    TIMEOUT = 30

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """
        Для Email токен не требуется.
        Просто возвращаем access_token если есть.
        """
        return connector.access_token

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Email не использует webhook в классическом смысле.
        Вместо этого используется IMAP polling через cron.

        Этот метод проверяет IMAP подключение.
        """
        imap_host = connector.imap_host
        imap_port = connector.imap_port or 993
        username = connector.email_username
        password = connector.email_password

        if not all([imap_host, username, password]):
            logger.warning("Email connector: IMAP not configured")
            return True  # Не ошибка - просто не настроен IMAP

        try:
            imap = aioimaplib.IMAP4_SSL(host=imap_host, port=imap_port)
            await imap.wait_hello_from_server()
            await imap.login(username, password)
            await imap.logout()

            logger.info(
                f"Email IMAP connection verified for connector {connector.id}"
            )
            return True
        except Exception as e:
            logger.error(f"Email IMAP connection failed: {e}")
            raise ValueError(f"IMAP connection error: {e}")

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """
        Email не использует webhook.
        """
        return {"ok": True}

    async def get_webhook_info(self, connector: "ChatConnector") -> dict:
        """
        Возвращает информацию о конфигурации Email.
        """
        return {
            "type": "email",
            "smtp_host": connector.smtp_host,
            "smtp_port": connector.smtp_port,
            "imap_host": connector.imap_host,
            "imap_port": connector.imap_port,
            "email_from": connector.email_from,
        }

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить email сообщение через SMTP.

        Args:
            connector: Коннектор Email
            user_from: Аккаунт отправителя
            body: HTML или текст сообщения
            chat_id: Email получателя (используется как chat_id)
            recipients_ids: Список email получателей

        Returns:
            Tuple[message_id, recipient_email]
        """
        smtp_host = connector.smtp_host
        smtp_port = connector.smtp_port or 587
        smtp_encryption = connector.smtp_encryption or "starttls"
        username = connector.email_username
        password = connector.email_password
        # email_from fallback to email_username (90% случаев одинаковые)
        email_from = connector.email_from or connector.email_username
        email_from_name = connector.email_from_name or ""

        if not all([smtp_host, username, password, email_from]):
            raise ValueError("SMTP not configured properly")

        # Определяем получателей
        recipients = []
        if chat_id:
            recipients.append(chat_id)
        if recipients_ids:
            recipients.extend(recipients_ids)

        if not recipients:
            raise ValueError("No recipients specified for email")

        # Создаём сообщение
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            connector.email_default_subject or "Message from FARA CRM"
        )
        msg["From"] = formataddr((email_from_name, email_from))
        msg["To"] = ", ".join(recipients)

        # Reply-To
        if connector.email_reply_to:
            msg["Reply-To"] = connector.email_reply_to

        # Return-Path для bounce tracking
        msg["Return-Path"] = connector.email_bounce or email_from

        # Добавляем текстовую и HTML версии
        plain_text = re.sub(r"<[^>]+>", "", body)
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))

        # Если body содержит HTML теги, добавляем HTML версию
        if "<" in body and ">" in body:
            msg.attach(MIMEText(body, "html", "utf-8"))

        # Генерируем Message-ID
        domain = email_from.split("@")[1] if "@" in email_from else "localhost"
        message_id = f"<{uuid.uuid4().hex}.{int(time.time())}@{domain}>"
        msg["Message-ID"] = message_id

        # Отправляем
        try:
            use_tls = smtp_encryption == "ssl"
            start_tls = smtp_encryption == "starttls"

            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=smtp_port,
                username=username,
                password=password,
                use_tls=use_tls,
                start_tls=start_tls,
                timeout=self.TIMEOUT,
            )

            logger.info(f"Email sent: {message_id} to {recipients}")
            return message_id, recipients[0]

        except Exception as e:
            logger.error(f"Email send error: {e}")
            raise ValueError(f"SMTP error: {e}")

    async def chat_send_message_binary(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        chat_id: str,
        attachment: "Attachment",
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить email с вложением.
        """
        smtp_host = connector.smtp_host
        smtp_port = connector.smtp_port or 587
        smtp_encryption = connector.smtp_encryption or "starttls"
        username = connector.email_username
        password = connector.email_password
        # email_from fallback to email_username (90% случаев одинаковые)
        email_from = connector.email_from or connector.email_username
        email_from_name = connector.email_from_name or ""

        if not all([smtp_host, username, password, email_from]):
            raise ValueError("SMTP not configured properly")

        recipients = [chat_id] if chat_id else []
        if recipients_ids:
            recipients.extend(recipients_ids)

        if not recipients:
            raise ValueError("No recipients specified for email")

        # Создаём multipart сообщение
        msg = MIMEMultipart()
        msg["Subject"] = connector.email_default_subject or "File from CRM"
        msg["From"] = formataddr((email_from_name, email_from))
        msg["To"] = ", ".join(recipients)

        # Reply-To
        if connector.email_reply_to:
            msg["Reply-To"] = connector.email_reply_to

        # Добавляем вложение
        file_content = attachment.content
        file_name = attachment.name
        mimetype = attachment.mimetype or "application/octet-stream"

        if file_content:
            maintype, subtype = (
                mimetype.split("/", 1)
                if "/" in mimetype
                else ("application", "octet-stream")
            )
            part = MIMEBase(maintype, subtype)
            part.set_payload(file_content)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {file_name}",
            )
            msg.attach(part)

        # Генерируем Message-ID
        domain = email_from.split("@")[1] if "@" in email_from else "localhost"
        message_id = f"<{uuid.uuid4().hex}.{int(time.time())}@{domain}>"
        msg["Message-ID"] = message_id

        # Отправляем
        try:
            use_tls = smtp_encryption == "ssl"
            start_tls = smtp_encryption == "starttls"

            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=smtp_port,
                username=username,
                password=password,
                use_tls=use_tls,
                start_tls=start_tls,
                timeout=self.TIMEOUT,
            )

            logger.info(
                f"Email with attachment sent: {message_id} to {recipients}"
            )
            return message_id, recipients[0]

        except Exception as e:
            logger.error(f"Email send error: {e}")
            raise ValueError(f"SMTP error: {e}")

    async def fetch_emails(
        self,
        connector: "ChatConnector",
        env: "Any",
        max_messages: int = 50,
    ) -> list[dict]:
        """
        Получить новые письма через IMAP polling.

        Используется для cron job.

        Args:
            connector: Email коннектор
            env: Environment
            max_messages: Максимальное число сообщений за раз (по умолчанию 50)

        Returns:
            Список сообщений для обработки
        """
        imap_host = connector.imap_host
        imap_port = connector.imap_port or 993
        username = connector.email_username
        password = connector.email_password
        last_uid = connector.imap_last_uid or 1

        if not all([imap_host, username, password]):
            logger.warning("Email IMAP not configured")
            return []

        messages = []
        new_max_uid = last_uid

        try:
            # Увеличиваем таймаут для больших писем
            imap = aioimaplib.IMAP4_SSL(
                host=imap_host, port=imap_port, timeout=60
            )
            await imap.wait_hello_from_server()
            await imap.login(username, password)

            # Открываем INBOX
            await imap.select("INBOX")

            # Первый запуск: last_uid = 0 или 1
            # Просто запоминаем последний UID и выходим
            is_first_run = last_uid <= 1

            if is_first_run:
                # Получаем UID последнего сообщения напрямую
                # FETCH * (UID) — '*' означает последнее сообщение в mailbox
                # Это O(1) вместо SEARCH ALL который возвращает все seq numbers
                fetch_resp = await imap.fetch("*", "(UID)")
                logger.debug(f"IMAP fetch * UID response: {fetch_resp}")

                if fetch_resp.result == "OK" and fetch_resp.lines:
                    # Парсим UID из ответа типа "1 FETCH (UID 12345)"
                    for line in fetch_resp.lines:
                        if isinstance(line, bytes):
                            line = line.decode()
                        if "UID" in line:
                            import re

                            match = re.search(r"UID\s+(\d+)", line)
                            if match:
                                max_uid = int(match.group(1))
                                connector.imap_last_uid = max_uid
                                await connector.update()
                                logger.info(
                                    f"Email first run: set last_uid to {max_uid}"
                                )
                                break

                await imap.logout()
                return []

            # Последующие запуски: получаем только новые письма
            # Используем IMAP search с критерием UID
            search_criteria = f"UID {last_uid + 1}:*"
            logger.info(f"IMAP searching with criteria: {search_criteria}")
            response = await imap.search(search_criteria)
            logger.info(
                f"IMAP search response: result={response.result}, lines={response.lines}"
            )

            # if response.result != "OK":
            #     # Если не поддерживается UID критерий - fallback на ALL
            #     logger.warning(f"IMAP search UID failed, trying ALL")
            #     response = await imap.search("ALL")
            #     logger.info(
            #         f"IMAP search ALL response: result={response.result}, lines={response.lines}"
            #     )

            # if response.result != "OK":
            #     logger.error(f"IMAP search failed: {response}")
            #     await imap.logout()
            #     return []

            # Парсим sequence numbers
            # Ответ в формате [b'123 456 789', b'SEARCH completed (Success)']
            seq_str = ""
            for line in response.lines:
                logger.debug(f"Response line: {type(line)} = {line}")
                if isinstance(line, bytes):
                    line = line.decode()
                # Ищем строку с числами (не содержит SEARCH/completed)
                if (
                    line
                    and line.strip()
                    and "SEARCH" not in line
                    and "completed" not in line.lower()
                ):
                    seq_str = line
                    break

            logger.info(f"Parsed seq_str: '{seq_str}'")
            seq_list = seq_str.strip().split() if seq_str else []
            logger.info(f"Parsed seq_list: {seq_list}")

            if not seq_list:
                logger.info(f"No new messages found (last_uid={last_uid})")
                await imap.logout()
                return []

            # Ограничиваем количество
            if len(seq_list) > max_messages:
                seq_list = seq_list[:max_messages]

            logger.info(f"Found {len(seq_list)} new messages to process")

            import re

            for seq in seq_list:
                try:
                    # Получаем UID и тело письма одним запросом
                    fetch_response = await imap.fetch(seq, "(UID BODY.PEEK[])")
                    logger.debug(
                        f"IMAP fetch response: {fetch_response.result}, lines count: {len(fetch_response.lines)}"
                    )

                    if (
                        fetch_response.result != "OK"
                        or not fetch_response.lines
                    ):
                        continue

                    # Парсим UID и тело из ответа
                    # Формат: [b'123 FETCH (UID 456 BODY[] {size}', <bytearray>, b')', b'Success']
                    uid_int = None
                    raw_email = None

                    for line in fetch_response.lines:
                        if isinstance(line, (bytearray, bytes)):
                            if isinstance(line, bytearray) or (
                                isinstance(line, bytes) and len(line) > 200
                            ):
                                # Это тело письма
                                raw_email = (
                                    bytes(line)
                                    if isinstance(line, bytearray)
                                    else line
                                )
                            elif isinstance(line, bytes):
                                # Может быть строка с UID
                                decoded = line.decode(errors="ignore")
                                if "UID" in decoded:
                                    match = re.search(r"UID\s+(\d+)", decoded)
                                    if match:
                                        uid_int = int(match.group(1))
                        elif isinstance(line, str) and "UID" in line:
                            match = re.search(r"UID\s+(\d+)", line)
                            if match:
                                uid_int = int(match.group(1))

                    logger.debug(
                        f"Parsed: uid={uid_int}, has_body={raw_email is not None}"
                    )

                    if not uid_int or uid_int <= last_uid:
                        logger.debug(
                            f"Skipping seq={seq}, uid={uid_int}, last_uid={last_uid}"
                        )
                        continue

                    if not raw_email:
                        logger.warning(
                            f"No body found for seq={seq}, uid={uid_int}"
                        )
                        continue

                    # Парсим письмо
                    email_message = message_from_bytes(raw_email)

                    messages.append(
                        {
                            "uid": uid_int,
                            "raw": raw_email,
                            "parsed": email_message,
                        }
                    )
                    logger.info(f"Successfully fetched email uid={uid_int}")

                    if uid_int > new_max_uid:
                        new_max_uid = uid_int

                except Exception as e:
                    logger.error(f"Error fetching seq={seq}: {e}")
                    continue

            await imap.logout()

            # Обновляем last_uid в коннекторе
            if new_max_uid > last_uid:
                connector.imap_last_uid = new_max_uid
                await connector.update()

            logger.info(f"Email fetched {len(messages)} new messages")
            return messages

        except Exception as e:
            logger.error(f"Email IMAP fetch error: {e}")
            return []

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> EmailMessageAdapter:
        """Создать адаптер для email сообщения."""
        return EmailMessageAdapter(connector, raw_message)

    async def handle_inbound_webhook(
        self,
        connector: "ChatConnector",
        payload: dict,
        env: "Any",
    ) -> dict:
        """
        Обработать входящий webhook от Mailgun/SendGrid Inbound Parse.

        Формат payload зависит от провайдера:
        - Mailgun: multipart form с полями sender, recipient, subject, body-plain, body-html
        - SendGrid: JSON с полями from, to, subject, text, html
        """
        return await self.handle_webhook(connector, payload, env)

    @classmethod
    async def cron_fetch_emails(cls, env: "Any") -> dict:
        """
        Cron job для получения новых email сообщений.

        Запускается периодически, проходит по всем активным
        email-коннекторам и получает новые письма через IMAP.

        Returns:
            Словарь с результатами: {"processed": int, "errors": int}
        """
        processed = 0
        errors = 0

        # Получаем все активные email-коннекторы с нужными полями
        connectors = await env.models.chat_connector.search(
            filter=[
                ("type", "=", "email"),
                ("active", "=", True),
            ],
            fields=[
                "id",
                "name",
                "type",
                "active",
                "imap_host",
                "imap_port",
                "email_username",
                "email_password",
                "imap_last_uid",
            ],
        )

        if not connectors:
            logger.info("No active email connectors found")
            return {"processed": 0, "errors": 0}

        strategy = cls()

        for connector in connectors:
            try:
                # Проверяем что IMAP настроен
                if not connector.imap_host or not connector.email_username:
                    logger.debug(
                        f"Connector {connector.id} IMAP not configured, skipping"
                    )
                    continue

                # Получаем новые письма
                messages = await strategy.fetch_emails(connector, env)

                if not messages:
                    continue

                # Обрабатываем каждое письмо
                for msg in messages:
                    try:
                        # Создаём адаптер и обрабатываем
                        adapter = strategy.create_message_adapter(
                            connector, msg
                        )

                        # Проверяем дубликат
                        is_duplicate = (
                            await env.models.chat_external_message.exists(
                                external_id=adapter.message_id,
                                connector_id=connector.id,
                            )
                        )

                        if is_duplicate:
                            logger.debug(
                                f"Duplicate email {adapter.message_id}, skipping"
                            )
                            continue

                        # Обрабатываем сообщение в транзакции
                        async with env.apps.db.get_transaction():
                            await strategy._process_incoming_message(
                                env, connector, adapter
                            )

                        processed += 1

                    except Exception as e:
                        logger.error(
                            f"Error processing email: {e}", exc_info=True
                        )
                        errors += 1

            except Exception as e:
                logger.error(
                    f"Error fetching emails from connector {connector.id}: {e}",
                    exc_info=True,
                )
                errors += 1

        logger.info(
            f"Email cron completed: processed={processed}, errors={errors}"
        )
        return {"processed": processed, "errors": errors}
