# Copyright 2025 FARA CRM
# Chat module - Email strategy (SMTP/IMAP)

import json
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
from ...chat.strategies.pipeline_incoming import IncomingMessagePipeline
from .adapter import EmailMessageAdapter

if TYPE_CHECKING:
    from backend.project_setup import ChatConnector
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)


def parse_email_body(body: str | None) -> tuple[str | None, str]:
    """
    Разобрать «email-формат» тела сообщения.

    Email хранит в body свой формат — JSON {"subject": "...", "html": "..."}
    (по аналогии с тем, как system-сообщение хранит {event, params}). Это
    позволяет не тащить subject отдельным параметром через общие методы
    отправки — тема едет внутри body, а парсит её только email-код.

    Возвращает (subject, html). Фолбэк для старых писем / чужого формата:
    если body не наш JSON — тема None, html = сам body (как раньше).
    """
    if not body:
        return None, ""
    try:
        data = json.loads(body)
        if isinstance(data, dict) and ("html" in data or "subject" in data):
            return data.get("subject"), data.get("html") or ""
    except (ValueError, TypeError):
        pass
    return None, body


_FETCH_MESSAGE_DATA_RE = re.compile(rb"[0-9]+ FETCH \(")
_UID_RE = re.compile(rb"\bUID\s+(\d+)")


def parse_fetch_response(lines: list) -> dict[int, bytes]:
    """
    Разобрать ответ IMAP FETCH в {uid: сырое письмо}.

    aioimaplib кладёт IMAP-литерал (синтаксис {N}) в Response.lines как
    bytearray, а любую другую строку ответа — как bytes. bytearray НЕ является
    подклассом bytes, поэтому типы не пересекаются, и проверка типа —
    точный признак «это тело письма», а не эвристика: на этом же различии
    стоит и сам aioimaplib (FetchCommand.wait_data фильтрует isinstance bytes,
    чтобы исключить тела из подсчёта скобок).

    Порога по длине не существует в принципе: строка-заголовок сверху не
    ограничена (BODYSTRUCTURE у multipart — сотни байт в одну строку), а
    литерал снизу не ограничен (`{0}` — легальное пустое тело). Диапазоны
    пересекаются, поэтому любое сравнение с константой ошибочно.

    Литерал всегда идёт сразу за своей строкой-заголовком `N FETCH (...`,
    поэтому UID берём из заголовка и связываем со СЛЕДУЮЩИМ элементом. Это
    корректно и для ответа сразу на несколько писем, где заголовки и тела
    чередуются в одном плоском списке.

    ВАЖНО: парность заголовок↔литерал верна, пока запрашивается ровно
    "(UID BODY.PEEK[])" — UID литералом не бывает, поэтому на письмо
    приходится строго один литерал. Добавление ENVELOPE / BODYSTRUCTURE /
    RFC822.HEADER / второй секции BODY[...] даст лишние литералы и сломает
    привязку.
    """
    result: dict[int, bytes] = {}

    for index, line in enumerate(lines):
        if not isinstance(line, bytes):
            continue
        if not _FETCH_MESSAGE_DATA_RE.match(line):
            continue

        match = _UID_RE.search(line)
        if not match:
            continue

        # Тело — только литерал, идущий непосредственно следом.
        if index + 1 < len(lines) and isinstance(lines[index + 1], bytearray):
            result[int(match.group(1))] = bytes(lines[index + 1])

    return result


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

    # Вложения приходят готовыми байтами внутри самого письма: качать их
    # неоткуда, в отличие от мессенджеров со ссылками.
    attachments_source = "content"

    # Вложения уезжают ВНУТРИ письма, а не отдельными сообщениями.
    #
    # База по умолчанию шлёт каждое вложение своим вызовом
    # chat_send_message_binary, и для мессенджеров это верно: в Telegram файл —
    # самостоятельное сообщение. Для почты — нет: «текст + 2 файла» уходило
    # ТРЕМЯ письмами, хотя формат ровно для этого и придуман (multipart/mixed).
    # С этим флагом база не крутит цикл, а отдаёт вложения в chat_send_message,
    # и получатель видит ОДНО письмо с прикреплёнными файлами.
    attachments_inline = True

    # Письмо умеет нести пометку «это ответ на такое-то» (заголовок
    # In-Reply-To) — почтовик получателя собирает переписку в одну ветку.
    # На маршрутизацию не влияет: ответ клиента вернёт нам наш Message-ID в
    # любом случае, его ставит почтовик клиента.
    supports_thread = True

    # Email адресуется своими полями (email_from/email_username), внешний
    # outbox-аккаунт ему не нужен. Без этого флага send_outgoing_message
    # молча пропускал отправку (у email connector.outbox_account_id = None,
    # т.к. external_account_id не заполняется) и письмо не уходило.
    requires_outbox_account = False

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

        if not imap_host or not username or not password:
            logger.warning("Email connector: IMAP not configured")
            return True  # Не ошибка - просто не настроен IMAP

        try:
            imap = aioimaplib.IMAP4_SSL(host=imap_host, port=imap_port)
            await imap.wait_hello_from_server()
            await imap.login(username, password)
            await imap.logout()

            logger.info(
                "Email IMAP connection verified for connector %s", connector.id
            )
            return True
        except Exception as e:
            logger.error("Email IMAP connection failed: %s", e)
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

    async def test_connection(self, connector: "ChatConnector") -> dict:
        """
        Проверить учётные данные почты: логин по SMTP и по IMAP.

        Позволяет пользователю в форме коннектора сразу увидеть, верный
        ли пароль/сервер, не дожидаясь первой отправки или cron-фетча.

        Проверяет оба канала независимо (SMTP и IMAP), чтобы точно
        показать, где именно проблема. Возвращает:
            {"ok": bool, "message": str, "details": {smtp: {...}, imap: {...}}}
        """
        username = connector.email_username
        password = connector.email_password

        if not username or not password:
            return {
                "ok": False,
                "message": "Укажите Email и пароль",
                "details": {},
            }

        smtp = await self._test_smtp(connector, username, password)
        imap = await self._test_imap(connector, username, password)

        # SMTP обязателен (отправка), IMAP опционален (получение).
        # Если IMAP-сервер не задан — не считаем это ошибкой.
        ok = smtp["ok"] and (imap["ok"] or imap.get("skipped"))

        if ok:
            message = "Соединение успешно"
            if imap.get("skipped"):
                message += " (IMAP не настроен — только отправка)"
        elif not smtp["ok"]:
            message = f"SMTP: {smtp['error']}"
        else:
            message = f"IMAP: {imap['error']}"

        return {
            "ok": ok,
            "message": message,
            "details": {"smtp": smtp, "imap": imap},
        }

    async def _test_smtp(
        self, connector: "ChatConnector", username: str, password: str
    ) -> dict:
        """Проверить SMTP-подключение и логин."""
        smtp_host = connector.smtp_host
        if not smtp_host:
            return {"ok": False, "error": "не указан SMTP-сервер"}

        smtp_port = connector.smtp_port or 587
        smtp_encryption = connector.smtp_encryption or "starttls"

        client = aiosmtplib.SMTP(
            hostname=smtp_host,
            port=smtp_port,
            use_tls=smtp_encryption == "ssl",
            start_tls=smtp_encryption == "starttls",
            timeout=self.TIMEOUT,
        )
        try:
            await client.connect()
            await client.login(username, password)
            await client.quit()
            return {"ok": True, "error": None}
        except Exception as e:
            logger.warning(
                "Email SMTP test failed for connector %s: %s",
                connector.id,
                e,
            )
            try:
                await client.quit()
            except Exception:
                pass
            return {"ok": False, "error": str(e)}

    async def _test_imap(
        self, connector: "ChatConnector", username: str, password: str
    ) -> dict:
        """Проверить IMAP-подключение и логин."""
        imap_host = connector.imap_host
        if not imap_host:
            # IMAP не настроен — это допустимо (только отправка).
            return {"ok": False, "error": None, "skipped": True}

        imap_port = connector.imap_port or 993

        try:
            imap = aioimaplib.IMAP4_SSL(
                host=imap_host, port=imap_port, timeout=self.TIMEOUT
            )
            await imap.wait_hello_from_server()
            resp = await imap.login(username, password)
            await imap.logout()
            if resp.result != "OK":
                return {"ok": False, "error": "логин отклонён сервером"}
            return {"ok": True, "error": None}
        except Exception as e:
            logger.warning(
                "Email IMAP test failed for connector %s: %s",
                connector.id,
                e,
            )
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _build_attachment_part(attachment: "Attachment"):
        """
        Собрать MIME-часть из вложения. None — если содержимого нет.

        Общая для обоих путей отправки: письмо с файлами (chat_send_message) и
        легаси-путь по одному файлу (chat_send_message_binary).
        """
        file_content = attachment.content
        if not file_content:
            return None

        file_name = attachment.name or "attachment"
        mimetype = attachment.mimetype or "application/octet-stream"
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
            "attachment",
            filename=file_name,
        )
        return part

    @staticmethod
    def _apply_thread_headers(msg, thread_message_id: str | None) -> None:
        """
        Пометить исходящее письмо ответом на последнее письмо этого чата.

        Зачем ТОЛЬКО это: почтовик получателя соберёт переписку в одну ветку —
        без заголовка каждое наше письмо висит у него в ящике отдельным.

        НА МАРШРУТИЗАЦИЮ НЕ ВЛИЯЕТ. Ответ клиента принесёт наш Message-ID в
        своём In-Reply-To независимо от того, ставим мы что-то или нет: его
        подставляет почтовик клиента. Поэтому достаточно одного id (последнего)
        и не нужен ни References, ни цепочка предков.
        """
        if thread_message_id:
            msg["In-Reply-To"] = thread_message_id

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
        thread_message_id: str | None = None,
        attachments: list["Attachment"] | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить email сообщение через SMTP — ОДНИМ письмом с вложениями.

        Args:
            connector: Коннектор Email
            user_from: Аккаунт отправителя
            body: email-формат {"subject","html"} (парсится ниже)
            chat_id: Email получателя (используется как chat_id)
            recipients_ids: Список email получателей
            thread_message_id: Message-ID последнего письма чата — уезжает в
                In-Reply-To, чтобы почтовик получателя собрал ветку.
            attachments: файлы В ЭТО ЖЕ письмо (см. attachments_inline).
                База отдаёт их сюда вместо цикла по chat_send_message_binary.

        Returns:
            Tuple[message_id, recipient_email]
        """
        # Тема и HTML едут внутри body (email-формат), а не отдельным
        # параметром — см. parse_email_body.
        subject, html = parse_email_body(body)

        smtp_host = connector.smtp_host
        smtp_port = connector.smtp_port or 587
        smtp_encryption = connector.smtp_encryption or "starttls"
        username = connector.email_username
        password = connector.email_password
        # From-адрес: ПО УМОЛЧАНИЮ = логин учётных данных (email_username).
        # Иначе Gmail и большинство SMTP блокируют письмо с «чужим» From,
        # не совпадающим с аутентифицированным ящиком. Если у коннектора задан
        # outbox-аккаунт (chat_external_account) — берём его адрес (санкц. алиас).
        outbox_from = user_from.external_id if user_from else None
        email_from = outbox_from or connector.email_username
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

        # Тело: plain + html как ВЗАИМОЗАМЕНЯЕМЫЕ версии одного текста —
        # multipart/alternative, почтовик показывает ту, что умеет.
        alternative = MIMEMultipart("alternative")
        plain_text = re.sub(r"<[^>]+>", "", html)
        alternative.attach(MIMEText(plain_text, "plain", "utf-8"))

        # Если html содержит теги, добавляем HTML версию
        if "<" in html and ">" in html:
            alternative.attach(MIMEText(html, "html", "utf-8"))

        if attachments:
            # Файлы — ДОПОЛНЕНИЕ к телу, а не альтернатива ему, поэтому
            # multipart/mixed снаружи: [тело, файл, файл]. Вкладывать их в
            # alternative нельзя — почтовик счёл бы их версиями текста.
            msg = MIMEMultipart("mixed")
            msg.attach(alternative)
            for att in attachments:
                part = self._build_attachment_part(att)
                if part is not None:
                    msg.attach(part)
        else:
            msg = alternative

        # Заголовки — на ВНЕШНЕМ контейнере (иначе уедут внутрь mixed и почтовик
        # их не увидит).
        # Subject: тема из body-формата (задаётся в виджете письма, дефолт —
        # имя чата) → email_default_subject коннектора → заглушка.
        msg["Subject"] = (
            subject
            or connector.email_default_subject
            or "Message from FARA CRM"
        )
        msg["From"] = formataddr((email_from_name, email_from))
        msg["To"] = ", ".join(recipients)

        # Reply-To
        if connector.email_reply_to:
            msg["Reply-To"] = connector.email_reply_to

        # Return-Path для bounce tracking
        msg["Return-Path"] = connector.email_bounce or email_from

        # Генерируем Message-ID.
        # ЭТО И ЕСТЬ КЛЮЧ МАРШРУТИЗАЦИИ ОТВЕТА: он сохраняется в
        # chat_external_message.external_id (create_link в send_outgoing_message)
        # вместе со ссылкой на внутреннее сообщение, а то знает свой чат. Когда
        # получатель ответит, его In-Reply-To вернёт нам этот же id → находим чат.
        #
        # uuid4 здесь НЕ косметика: ключ должен быть непредсказуемым. Если
        # закодировать сюда chat_id, ключ станет перечислимым — любой смог бы
        # подобрать In-Reply-To и вписаться в чужой чат. (У Odoo в Message-ID
        # есть строка вида -openerp-42-crm.lead, но она инертна: инбаунд её не
        # парсит.) Не кодировать сюда ничего осмысленного.
        domain = email_from.split("@")[1] if "@" in email_from else "localhost"
        message_id = f"<{uuid.uuid4().hex}.{int(time.time())}@{domain}>"
        msg["Message-ID"] = message_id

        # Цепочка: сшивает ветку у получателя и возвращается к нам в его ответе.
        self._apply_thread_headers(msg, thread_message_id)

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

            logger.info("Email sent: %s to %s", message_id, recipients)
            return message_id, recipients[0]

        except Exception as e:
            logger.error("Email send error: %s", e)
            raise ValueError(f"SMTP error: {e}")

    async def chat_send_message_binary(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        chat_id: str,
        attachment: "Attachment",
        recipients_ids: list | None = None,
        thread_message_id: str | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить email с вложением.

        ВНИМАНИЕ: база (send_outgoing_message) зовёт этот метод ОТДЕЛЬНО НА
        КАЖДОЕ вложение, а текст уходит ещё одним письмом. То есть «текст + 2
        файла» = 3 письма. Для мессенджеров это верно (там файл — отдельное
        сообщение), для почты — нет: нормой было бы одно письмо с вложениями.
        Пока это не переделано, thread_message_id хотя бы сшивает их в ОДНУ
        ВЕТКУ у получателя, а не рассыпает по ящику.
        """
        smtp_host = connector.smtp_host
        smtp_port = connector.smtp_port or 587
        smtp_encryption = connector.smtp_encryption or "starttls"
        username = connector.email_username
        password = connector.email_password
        # From-адрес: ПО УМОЛЧАНИЮ = логин учётных данных (email_username).
        # Иначе Gmail и большинство SMTP блокируют письмо с «чужим» From,
        # не совпадающим с аутентифицированным ящиком. Если у коннектора задан
        # outbox-аккаунт (chat_external_account) — берём его адрес (санкц. алиас).
        outbox_from = user_from.external_id if user_from else None
        email_from = outbox_from or connector.email_username
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

        # Генерируем Message-ID — он же ключ маршрутизации ответа, см. коммент
        # в chat_send_message. Ничего осмысленного внутрь не кодируем.
        domain = email_from.split("@")[1] if "@" in email_from else "localhost"
        message_id = f"<{uuid.uuid4().hex}.{int(time.time())}@{domain}>"
        msg["Message-ID"] = message_id

        # Цепочка — та же, что у текстового письма этого же сообщения: письма
        # получаются разными, но ветка у получателя одна.
        self._apply_thread_headers(msg, thread_message_id)

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
                "Email with attachment sent: %s to %s", message_id, recipients
            )
            return message_id, recipients[0]

        except Exception as e:
            logger.error("Email send error: %s", e)
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

        ВАЖНО: watermark (connector.imap_last_uid) здесь НЕ двигается — это
        делает cron_fetch_emails ПОСЛЕ успешной обработки каждого письма.
        Раньше он персистился прямо здесь, сразу после удачного FETCH, и любое
        падение обработки
        теряло письмо НАВСЕГДА: watermark уже уехал, а на следующем опросе
        "UID <uid+1>:*" по правилу n:* вернёт то же письмо, и фильтр
        u > last_uid его отсечёт. Загрузить письмо и обработать письмо — разные
        события, и отмечать прогресс можно только по второму.

        Args:
            connector: Email коннектор
            env: Environment
            max_messages: Максимальное число сообщений за раз (по умолчанию 50)

        Returns:
            Список сообщений (uid по возрастанию) для обработки
        """
        imap_host = connector.imap_host
        imap_port = connector.imap_port or 993
        username = connector.email_username
        password = connector.email_password
        last_uid = connector.imap_last_uid or 1

        if not imap_host or not username or not password:
            logger.warning("Email IMAP not configured")
            return []

        messages = []

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
                logger.debug("IMAP fetch * UID response: %s", fetch_resp)

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
                                await connector.update(
                                    type(connector)(imap_last_uid=max_uid)
                                )
                                logger.info(
                                    "Email first run: set last_uid to %s",
                                    max_uid,
                                )
                                break

                await imap.logout()
                return []

            # Последующие запуски: получаем только новые письма.
            # UID SEARCH, а не SEARCH: возвращает UID'ы вместо порядковых
            # номеров, поэтому дальше адресуемся по UID и не зависим от
            # перенумерации при EXPUNGE. RFC 3501 §7.4.1 запрещает серверу
            # слать EXPUNGE во время SEARCH/FETCH, но UID-команды этой гарантии
            # не требуют — им она и не нужна.
            # charset=None: CHARSET необязателен (RFC 3501 §6.4.4), а часть
            # серверов отвечает NO на "SEARCH CHARSET utf-8".
            search_criteria = f"UID {last_uid + 1}:*"
            logger.info("IMAP searching with criteria: %s", search_criteria)
            response = await imap.uid_search(search_criteria, charset=None)
            logger.info(
                "IMAP search response: result=%s, lines=%s",
                response.result,
                response.lines,
            )

            if response.result != "OK":
                logger.error("IMAP UID SEARCH failed: %s", response)
                await imap.logout()
                return []

            # Парсим UID'ы
            # Ответ в формате [b'123 456 789', b'SEARCH completed (Success)']
            uid_str = ""
            for line in response.lines:
                logger.debug("Response line: %s = %s", type(line), line)
                if isinstance(line, bytes):
                    line = line.decode()
                # Ищем строку с числами (не содержит SEARCH/completed)
                if (
                    line
                    and line.strip()
                    and "SEARCH" not in line
                    and "completed" not in line.lower()
                ):
                    uid_str = line
                    break

            logger.info("Parsed uid_str: '%s'", uid_str)

            try:
                uid_list = [int(u) for u in uid_str.split()]
            except ValueError:
                logger.error("Unexpected UID SEARCH payload: %r", uid_str)
                await imap.logout()
                return []

            # RFC 3501 §6.4.8: диапазон с '*' ("UID n:*") ВСЕГДА матчит хотя бы
            # одно письмо — с максимальным UID, даже если тот меньше n. Поэтому
            # отсекаем уже известные UID'ы ДО фетча: иначе каждый холостой опрос
            # тянет тело письма целиком по сети и тут же его выбрасывает.
            uid_list = sorted(u for u in uid_list if u > last_uid)
            logger.info("Parsed uid_list (new only): %s", uid_list)

            if not uid_list:
                logger.info("No new messages found (last_uid=%s)", last_uid)
                await imap.logout()
                return []

            # Ограничиваем количество
            if len(uid_list) > max_messages:
                uid_list = uid_list[:max_messages]

            logger.info("Found %s new messages to process", len(uid_list))

            for uid_int in uid_list:
                try:
                    # UID FETCH: адресуемся по UID, а не по порядковому номеру.
                    # Спека "(UID BODY.PEEK[])" — ровно один литерал на письмо,
                    # см. требование в parse_fetch_response.
                    fetch_response = await imap.uid(
                        "fetch", str(uid_int), "(UID BODY.PEEK[])"
                    )
                    logger.debug(
                        "IMAP fetch response: %s, lines count: %s",
                        fetch_response.result,
                        len(fetch_response.lines),
                    )

                    if fetch_response.result != "OK":
                        logger.warning(
                            "IMAP UID FETCH %s failed: %s",
                            uid_int,
                            fetch_response,
                        )
                        break

                    raw_email = parse_fetch_response(fetch_response.lines).get(
                        uid_int
                    )

                    if raw_email is None:
                        # Письмо удалено между SEARCH и FETCH, либо сервер
                        # ответил без message data.
                        logger.warning("No body found for uid=%s", uid_int)
                        break

                    # Парсим письмо
                    email_message = message_from_bytes(raw_email)

                    messages.append(
                        {
                            "uid": uid_int,
                            "raw": raw_email,
                            "parsed": email_message,
                        }
                    )
                    logger.info("Successfully fetched email uid=%s", uid_int)

                except Exception as e:
                    # Рвём цикл, а не continue: письма отдаём вызывающему
                    # НЕПРЕРЫВНОЙ чередой по возрастанию uid, чтобы он мог
                    # двигать watermark по последнему успешно ОБРАБОТАННОМУ.
                    # При continue дырка в середине была бы не видна.
                    logger.error("Error fetching uid=%s: %s", uid_int, e)
                    break

            await imap.logout()

            logger.info("Email fetched %s new messages", len(messages))
            return messages

        except Exception as e:
            logger.error("Email IMAP fetch error: %s", e)
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

        connectors = await env.models.chat_connector.search(
            filter=[
                ("type", "=", "email"),
                ("active", "=", True),
            ],
            fields_nested={
                "contact_type_id": {
                    "fields": ["id", "name", "is_phone_format"]
                },
                "outbox_account_id": {"fields": ["id", "external_id"]},
            },
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
                        "Connector %s IMAP not configured, skipping",
                        connector.id,
                    )
                    continue

                # Получаем новые письма — непрерывной чередой по возрастанию uid
                messages = await strategy.fetch_emails(connector, env)

                if not messages:
                    continue

                # Watermark двигаем ТОЛЬКО по последнему успешно ОБРАБОТАННОМУ
                # письму и только по непрерывной череде: первое же падение
                # обрывает цикл, чтобы сбойное письмо перезапросилось на
                # следующем опросе, а не потерялось навсегда. Раньше watermark
                # персистился в fetch_emails сразу после загрузки — и любая
                # ошибка обработки съедала письмо (так пропало uid=3239).
                last_ok_uid = None

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
                                "Duplicate email %s, skipping",
                                adapter.message_id,
                            )
                            # Уже обработано раньше — череда не рвётся.
                            last_ok_uid = msg["uid"]
                            continue

                        # Обрабатываем сообщение в транзакции
                        async with env.apps.db.get_transaction():
                            await IncomingMessagePipeline(
                                strategy, env, connector, adapter
                            ).run()

                        processed += 1
                        last_ok_uid = msg["uid"]

                    except Exception as e:
                        errors += 1
                        # НЕ continue: иначе следующее успешное письмо сдвинет
                        # watermark за это, и оно не вернётся уже никогда.
                        #
                        # РАЗМЕН, о котором надо знать: письмо, падающее
                        # ПОСТОЯННО, блокирует всю последующую почту этого
                        # коннектора (head-of-line blocking) — пока причина не
                        # устранена, письма за ним не доставятся. Это выбрано
                        # сознательно: блокировка громкая и обратимая, а прежняя
                        # тихая потеря — нет. Поэтому лог ERROR явно говорит,
                        # что очередь встала, и называет uid.
                        # TODO: ограниченные ретраи + dead-letter (нужна колонка
                        # со счётчиком попыток), чтобы «ядовитое» письмо
                        # пропускалось после N неудач с алертом.
                        logger.error(
                            "Email queue BLOCKED at uid=%s (connector %s): %s. "
                            "Письма с бОльшим uid не будут обработаны, пока "
                            "это не починено. Watermark остаётся на uid=%s.",
                            msg.get("uid"),
                            connector.id,
                            e,
                            (
                                last_ok_uid
                                if last_ok_uid is not None
                                else (connector.imap_last_uid or 1)
                            ),
                            exc_info=True,
                        )
                        break

                if last_ok_uid is not None and last_ok_uid > (
                    connector.imap_last_uid or 1
                ):
                    await connector.update(
                        type(connector)(imap_last_uid=last_ok_uid)
                    )
                    logger.info(
                        "Email watermark advanced to uid=%s (connector %s)",
                        last_ok_uid,
                        connector.id,
                    )

            except Exception as e:
                logger.error(
                    "Error fetching emails from connector %s: %s",
                    connector.id,
                    e,
                    exc_info=True,
                )
                errors += 1

        logger.info(
            "Email cron completed: processed=%s, errors=%s", processed, errors
        )
        return {"processed": processed, "errors": errors}
