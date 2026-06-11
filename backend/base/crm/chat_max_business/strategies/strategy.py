# Copyright 2025 FARA CRM
# Chat module - MAX official business API strategy (platform-api.max.ru)

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, Tuple

import httpx

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
from .adapter import MaxBusinessMessageAdapter

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)


class MaxBusinessStrategy(ChatStrategyBase):
    """
    Стратегия ОФИЦИАЛЬНОЙ бизнес-интеграции MAX (platform-api.max.ru).

    Ключевое отличие от бот-канала (chat_max): верифицированный бизнес-аккаунт
    может писать клиенту ПЕРВЫМ по номеру телефона — санкционировано
    платформой. Webhook и объект Update — те же, что в Bot API.

    Настройки коннектора:
    - access_token: токен бизнес-аккаунта (business.max.ru, после
      верификации через Госуслуги/банк)
    - connector_url: https://platform-api.max.ru (по умолчанию)
    - webhook_url: устанавливается через POST /subscriptions (кнопка в форме)

    Авторизация: заголовок Authorization со значением access_token.
    Лимит платформы: до 30 rps.

    ВНИМАНИЕ: метод «отправка по номеру телефона» официального бизнес-API на
    момент написания гейтован бизнес-верификацией (GA «MAX для бизнеса» —
    I кв. 2026) и публично не специфицирован. Отправка реализована на общих
    конвенциях platform-api.max.ru (POST /messages с адресацией phone/chat_id);
    точный параметр/эндпоинт подтвердить в кабинете после верификации —
    см. _recipient_params().

    Документация: https://dev.max.ru/docs-api
    """

    strategy_type = "max_business"
    BASE_API_URL = "https://platform-api.max.ru"
    TIMEOUT = 30.0
    UPLOAD_RETRY = 4
    UPLOAD_RETRY_DELAY = 1.5

    # ========================================================================
    # Вспомогательные методы
    # ========================================================================

    def _base_url(self, connector: "ChatConnector") -> str:
        return (connector.connector_url or self.BASE_API_URL).rstrip("/")

    def _api_url(self, connector: "ChatConnector", method: str) -> str:
        return f"{self._base_url(connector)}/{method.lstrip('/')}"

    @staticmethod
    def _headers(connector: "ChatConnector") -> dict:
        """Официальный API авторизуется заголовком Authorization=access_token."""
        return {"Authorization": connector.access_token or ""}

    @staticmethod
    def _recipient_params(value: Any) -> dict:
        """
        Параметры адресации получателя для POST /messages.

        Бизнес-канал адресует по НОМЕРУ ТЕЛЕФОНА (write-first). Эвристика:
        если значение похоже на телефон (10–15 цифр, без ведущего '-') —
        шлём по ?phone=, иначе считаем это chat_id существующей переписки.

        TODO(business): подтвердить точный параметр отправки по номеру в
        официальной доке/кабинете после бизнес-верификации.
        """
        raw = str(value or "").strip()
        digits = re.sub(r"\D", "", raw)
        if not raw.startswith("-") and 10 <= len(digits) <= 15:
            return {"phone": digits}
        return {"chat_id": raw}

    @staticmethod
    def _parse(response: httpx.Response, action: str) -> dict:
        try:
            result = response.json()
        except Exception:  # noqa: BLE001
            result = {}
        if response.status_code >= 400:
            message = ""
            if isinstance(result, dict):
                message = result.get("message") or result.get("code") or ""
            raise ValueError(
                f"MAX business {action}: HTTP {response.status_code} "
                f"{message or (response.text or '')[:200]}"
            )
        return result if isinstance(result, dict) else {}

    @staticmethod
    def _extract_mid(result: dict) -> str:
        message = result.get("message", {}) or {}
        body = message.get("body", {}) or {}
        return str(body.get("mid", "") or result.get("mid", ""))

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """Токен бизнес-аккаунта статический — возвращаем access_token."""
        return connector.access_token

    # ========================================================================
    # Webhook (официально через /subscriptions)
    # ========================================================================

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """Подписаться на обновления. MAX API: POST /subscriptions."""
        url = self._api_url(connector, "subscriptions")
        payload: dict[str, Any] = {
            "url": connector.webhook_url,
            "update_types": ["message_created"],
        }
        if connector.webhook_hash:
            payload["secret"] = connector.webhook_hash

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                url, headers=self._headers(connector), json=payload
            )
            self._parse(response, "setWebhook")

        logger.info("MAX business webhook set for connector %s", connector.id)
        return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """Отписаться. MAX API: DELETE /subscriptions?url=..."""
        url = self._api_url(connector, "subscriptions")
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.delete(
                url,
                headers=self._headers(connector),
                params={"url": connector.webhook_url},
            )
            result = self._parse(response, "deleteWebhook")

        logger.info(
            "MAX business webhook deleted for connector %s", connector.id
        )
        return result

    async def get_webhook_info(self, connector: "ChatConnector") -> dict:
        """Список подписок. MAX API: GET /subscriptions."""
        url = self._api_url(connector, "subscriptions")
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url, headers=self._headers(connector))
            return self._parse(response, "getSubscriptions")

    async def get_self_account_id(self, connector: "ChatConnector") -> dict:
        """Информация о бизнес-аккаунте. MAX API: GET /me."""
        url = self._api_url(connector, "me")
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url, headers=self._headers(connector))
            return self._parse(response, "getMe")

    # ========================================================================
    # Отправка сообщений
    # ========================================================================

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить текст. Можно ПЕРВЫМ — по номеру телефона.

        MAX API: POST /messages?phone=<номер>  (write-first)
                 либо ?chat_id=<id>            (ответ в существующий чат)

        chat_id здесь — это телефон (для первого сообщения / переписки,
        ключуемой по номеру) либо chat_id существующего чата.
        """
        if not chat_id:
            raise ValueError(
                "Cannot send MAX business message without recipient"
            )

        clean_text = re.sub(r"<[^>]+>", "", body or "")

        url = self._api_url(connector, "messages")
        params = self._recipient_params(chat_id)
        # Канонический ключ переписки (цифры телефона или chat_id) — его же
        # вернём как external_chat_id, чтобы совпасть с ключом из webhook.
        key = params.get("phone") or params.get("chat_id") or str(chat_id)

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                url,
                headers=self._headers(connector),
                params=params,
                json={"text": clean_text},
            )
            result = self._parse(response, "sendMessage")

        msg_id = self._extract_mid(result)
        logger.info("MAX business message sent: %s to %s", msg_id, key)
        return msg_id, str(key)

    async def chat_send_message_binary(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        chat_id: str,
        attachment: "Attachment",
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить файл/изображение (официальные uploads, как в Bot API):
        POST /uploads?type=... -> залить бинарь -> POST /messages с attachments.
        Адресация — по номеру/chat_id (см. _recipient_params).
        """
        if not chat_id:
            raise ValueError("Cannot send MAX business file without recipient")

        mimetype = attachment.mimetype or ""
        att_type = self._attachment_type(mimetype)

        content = attachment.content
        if content is None and hasattr(attachment, "read_content"):
            content = await attachment.read_content()
        if content is None:
            raise ValueError("Attachment has no content")

        payload = await self._upload_attachment(
            connector, att_type, attachment.name, content, mimetype
        )

        url = self._api_url(connector, "messages")
        params = self._recipient_params(chat_id)
        key = params.get("phone") or params.get("chat_id") or str(chat_id)
        message_body = {
            "attachments": [{"type": att_type, "payload": payload}]
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            for _ in range(self.UPLOAD_RETRY):
                response = await client.post(
                    url,
                    headers=self._headers(connector),
                    params=params,
                    json=message_body,
                )
                if response.status_code < 400:
                    result = self._parse(response, "sendMessage(file)")
                    msg_id = self._extract_mid(result)
                    logger.info(
                        "MAX business %s sent: %s to %s",
                        att_type,
                        msg_id,
                        key,
                    )
                    return msg_id, str(key)

                text = response.text or ""
                if "not.ready" in text:
                    last_error = ValueError(text)
                    await asyncio.sleep(self.UPLOAD_RETRY_DELAY)
                    continue
                self._parse(response, "sendMessage(file)")

        raise ValueError(
            f"MAX business sendMessage(file) failed after retries: {last_error}"
        )

    async def _upload_attachment(
        self,
        connector: "ChatConnector",
        att_type: str,
        filename: str,
        content: bytes,
        mimetype: str,
    ) -> dict:
        """POST /uploads?type=... -> залив бинаря -> payload для attachments."""
        uploads_url = self._api_url(connector, "uploads")
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                uploads_url,
                headers=self._headers(connector),
                params={"type": att_type},
            )
            upload_info = self._parse(response, "uploads")

        upload_target = upload_info.get("url")
        if not upload_target:
            raise ValueError(f"MAX business uploads: no url in {upload_info}")

        files = {
            "data": (filename, content, mimetype or "application/octet-stream")
        }
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(upload_target, files=files)
            upload_result = self._parse(response, "uploadBinary")

        if upload_result.get("photos"):
            return {"photos": upload_result["photos"]}
        if upload_result.get("token"):
            return {"token": upload_result["token"]}
        if upload_info.get("token"):
            return {"token": upload_info["token"]}
        raise ValueError(
            f"MAX business upload: cannot resolve token from {upload_result}"
        )

    # ========================================================================
    # Утилиты
    # ========================================================================

    @staticmethod
    def _attachment_type(mimetype: str) -> str:
        mimetype = mimetype or ""
        if mimetype.startswith("image/"):
            return "image"
        if mimetype.startswith("video/"):
            return "video"
        if mimetype.startswith("audio/"):
            return "audio"
        return "file"

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> MaxBusinessMessageAdapter:
        return MaxBusinessMessageAdapter(connector, raw_message)
