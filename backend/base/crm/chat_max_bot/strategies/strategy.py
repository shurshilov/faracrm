# Copyright 2025 FARA CRM
# Chat module - MAX (МАКС) strategy

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, Tuple

import httpx

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
from .adapter import MaxBotMessageAdapter

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)


class MaxBotStrategy(ChatStrategyBase):
    """
    Стратегия для интеграции с мессенджером MAX (МАКС) Bot API.

    Поддерживает:
    - Приём сообщений через webhook (подписки /subscriptions)
    - Отправку текстовых сообщений
    - Отправку изображений/файлов (через uploads)
    - Скачивание входящих вложений (по прямым URL)

    Требует настройки коннектора:
    - access_token: токен бота (выдаётся @MasterBot в MAX)
    - connector_url: https://botapi.max.ru (по умолчанию)
    - webhook_url: URL для приёма обновлений (HTTPS обязателен)
    - external_account_id: user_id бота (можно получить кнопкой в форме —
      метод GET /me)

    Документация API: https://dev.max.ru/docs-api
    """

    strategy_type = "max_bot"
    BASE_API_URL = "https://botapi.max.ru"
    TIMEOUT = 30.0
    # Сколько раз повторить отправку вложения, если MAX ещё не обработал файл.
    UPLOAD_RETRY = 4
    UPLOAD_RETRY_DELAY = 1.5

    # ========================================================================
    # Вспомогательные методы
    # ========================================================================

    def _base_url(self, connector: "ChatConnector") -> str:
        """База API без хвостового слеша."""
        return (connector.connector_url or self.BASE_API_URL).rstrip("/")

    def _api_url(self, connector: "ChatConnector", method: str) -> str:
        """Сформировать URL метода API."""
        return f"{self._base_url(connector)}/{method.lstrip('/')}"

    def _auth_params(self, connector: "ChatConnector", **extra: Any) -> dict:
        """Параметры запроса с access_token (MAX принимает токен в query)."""
        params: dict[str, Any] = {"access_token": connector.access_token or ""}
        for key, value in extra.items():
            if value is not None:
                params[key] = value
        return params

    @staticmethod
    def _raise_for_error(response: httpx.Response, action: str) -> dict:
        """Проверить ответ MAX и вернуть json или бросить ValueError."""
        try:
            result = response.json()
        except Exception:  # noqa: BLE001
            result = {}

        if response.status_code >= 400:
            message = ""
            if isinstance(result, dict):
                message = result.get("message") or result.get("code") or ""
            raise ValueError(
                f"MAX {action} error: HTTP {response.status_code} "
                f"{message or response.text}"
            )
        return result if isinstance(result, dict) else {}

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """
        Для MAX токен бота статический и не требует обновления.
        Просто возвращаем существующий access_token.
        """
        return connector.access_token

    # ========================================================================
    # Webhook (подписки)
    # ========================================================================

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Подписаться на обновления через webhook.

        MAX API: POST /subscriptions
        https://dev.max.ru/docs-api/methods/POST/subscriptions
        """
        url = self._api_url(connector, "subscriptions")

        payload: dict[str, Any] = {
            "url": connector.webhook_url,
            "update_types": ["message_created"],
        }
        # webhook_hash подходит под ограничения secret (A-Z, a-z, 0-9, дефис)
        # и приходит в заголовке X-Max-Bot-Api-Secret — дополнительная защита.
        if connector.webhook_hash:
            payload["secret"] = connector.webhook_hash

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                url, params=self._auth_params(connector), json=payload
            )
            self._raise_for_error(response, "setWebhook")

        logger.info(
            "MAX webhook set successfully for connector %s", connector.id
        )
        return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """
        Отписаться от обновлений.

        MAX API: DELETE /subscriptions?url=...
        """
        url = self._api_url(connector, "subscriptions")

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.delete(
                url,
                params=self._auth_params(connector, url=connector.webhook_url),
            )
            result = self._raise_for_error(response, "deleteWebhook")

        logger.info("MAX webhook deleted for connector %s", connector.id)
        return result

    async def get_webhook_info(self, connector: "ChatConnector") -> dict:
        """
        Получить список активных подписок.

        MAX API: GET /subscriptions
        """
        url = self._api_url(connector, "subscriptions")

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(
                url, params=self._auth_params(connector)
            )
            return self._raise_for_error(response, "getSubscriptions")

    async def get_self_account_id(self, connector: "ChatConnector") -> dict:
        """
        Получить информацию о боте (для заполнения external_account_id).

        MAX API: GET /me
        """
        url = self._api_url(connector, "me")

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(
                url, params=self._auth_params(connector)
            )
            return self._raise_for_error(response, "getMe")

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
        Отправить текстовое сообщение в MAX.

        MAX API: POST /messages?chat_id=...
        https://dev.max.ru/docs-api/methods/POST/messages

        Args:
            connector: Коннектор MAX
            user_from: Аккаунт отправителя (не используется для MAX)
            body: Текст сообщения (до 4000 символов)
            chat_id: ID чата MAX
            recipients_ids: Не используется

        Returns:
            Tuple[message_id, chat_id]
        """
        if not chat_id:
            raise ValueError("Cannot send MAX message without chat_id")

        url = self._api_url(connector, "messages")

        # Удаляем HTML теги из текста — отправляем как обычный текст.
        clean_text = re.sub(r"<[^>]+>", "", body)

        payload = {"text": clean_text}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                url,
                params=self._auth_params(connector, chat_id=chat_id),
                json=payload,
            )
            result = self._raise_for_error(response, "sendMessage")

        message_id = self._extract_mid(result)

        logger.info("MAX message sent: %s to chat %s", message_id, chat_id)
        return message_id, str(chat_id)

    async def chat_send_message_binary(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        chat_id: str,
        attachment: "Attachment",
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить изображение/видео/аудио/файл в MAX.

        Процесс (3 шага):
        1. POST /uploads?type=... → получить upload url
        2. POST файла на upload url → получить token (или photos)
        3. POST /messages с attachments=[{type, payload}]

        MAX может не успеть обработать файл к моменту отправки — тогда вернёт
        ошибку "attachment.not.ready", поэтому шаг 3 повторяется с задержкой.
        """
        if not chat_id:
            raise ValueError("Cannot send MAX file without chat_id")

        mimetype = attachment.mimetype or ""
        att_type = self._attachment_type(mimetype)

        # Содержимое файла (как в Avito — на случай ленивой загрузки content).
        content = attachment.content
        if content is None and hasattr(attachment, "read_content"):
            content = await attachment.read_content()
        if content is None:
            raise ValueError("Attachment has no content")

        # Шаг 1 + 2: загрузка файла, получаем payload для attachments.
        payload = await self._upload_attachment(
            connector, att_type, attachment.name, content, mimetype
        )

        # Шаг 3: отправка сообщения с вложением (с ретраями на not.ready).
        url = self._api_url(connector, "messages")
        message_body = {
            "attachments": [{"type": att_type, "payload": payload}]
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            for attempt in range(self.UPLOAD_RETRY):
                response = await client.post(
                    url,
                    params=self._auth_params(connector, chat_id=chat_id),
                    json=message_body,
                )
                if response.status_code < 400:
                    result = self._raise_for_error(response, "sendMessage")
                    message_id = self._extract_mid(result)
                    logger.info(
                        "MAX %s sent: %s to chat %s",
                        att_type,
                        message_id,
                        chat_id,
                    )
                    return message_id, str(chat_id)

                # Если файл ещё не готов — ждём и пробуем снова.
                text = response.text or ""
                if "not.ready" in text or "attachment.not.ready" in text:
                    last_error = ValueError(text)
                    await asyncio.sleep(self.UPLOAD_RETRY_DELAY)
                    continue

                # Иная ошибка — прекращаем.
                self._raise_for_error(response, "sendMessage")

        raise ValueError(
            f"MAX sendMessage(file) failed after retries: {last_error}"
        )

    async def _upload_attachment(
        self,
        connector: "ChatConnector",
        att_type: str,
        filename: str,
        content: bytes,
        mimetype: str,
    ) -> dict:
        """
        Загрузить файл в MAX и вернуть payload для attachments.

        Шаг 1: POST /uploads?type=... → {"url": "..."}
        Шаг 2: POST файла на полученный url → {"token": "..."} либо
               {"photos": {"<key>": {"token": "..."}}} для изображений.
        """
        # Шаг 1 — получаем endpoint для загрузки.
        uploads_url = self._api_url(connector, "uploads")
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                uploads_url,
                params=self._auth_params(connector, type=att_type),
            )
            upload_info = self._raise_for_error(response, "uploads")

        upload_target = upload_info.get("url")
        if not upload_target:
            raise ValueError(f"MAX uploads: no url in response {upload_info}")

        # Шаг 2 — заливаем бинарь.
        files = {
            "data": (filename, content, mimetype or "application/octet-stream")
        }
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(upload_target, files=files)
            upload_result = self._raise_for_error(response, "uploadBinary")

        # Изображения возвращают структуру photos, остальное — token.
        if upload_result.get("photos"):
            return {"photos": upload_result["photos"]}
        if upload_result.get("token"):
            return {"token": upload_result["token"]}
        # Иногда токен лежит на верхнем уровне как id/fileId.
        if upload_info.get("token"):
            return {"token": upload_info["token"]}

        raise ValueError(
            f"MAX upload: cannot resolve token from {upload_result}"
        )

    # ========================================================================
    # Утилиты
    # ========================================================================

    @staticmethod
    def _attachment_type(mimetype: str) -> str:
        """Определить тип вложения MAX по mimetype."""
        mimetype = mimetype or ""
        if mimetype.startswith("image/"):
            return "image"
        if mimetype.startswith("video/"):
            return "video"
        if mimetype.startswith("audio/"):
            return "audio"
        return "file"

    @staticmethod
    def _extract_mid(result: dict) -> str:
        """Достать id отправленного сообщения из ответа MAX."""
        # Ответ: {"message": {"body": {"mid": "..."}, ...}}
        message = result.get("message", {}) or {}
        body = message.get("body", {}) or {}
        return str(body.get("mid", "") or result.get("mid", ""))

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> MaxBotMessageAdapter:
        """Создать адаптер для сообщения MAX."""
        return MaxBotMessageAdapter(connector, raw_message)
