# Copyright 2025 FARA CRM
# Chat module - Telegram strategy

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Tuple

import httpx

from ...attachments.models.attachments import Attachment
from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
from .adapter import TelegramMessageAdapter


if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )

logger = logging.getLogger(__name__)


class TelegramStrategy(ChatStrategyBase):
    """
    Стратегия для интеграции с Telegram Bot API.

    Поддерживает:
    - Приём сообщений через webhook
    - Отправку текстовых сообщений
    - Отправку изображений
    - Скачивание файлов

    Требует настройки:
    - access_token: токен бота (без "bot" префикса)
    - connector_url: https://api.telegram.org
    - webhook_url: URL для приёма обновлений
    """

    strategy_type = "telegram"
    BASE_API_URL = "https://api.telegram.org"
    TIMEOUT = 30.0

    def _get_api_url(self, connector: "ChatConnector", method: str) -> str:
        """Формирует URL для API запроса."""
        token = f"bot{connector.access_token}"
        base_url = connector.connector_url or self.BASE_API_URL
        return f"{base_url}/{token}/{method}"

    def _get_file_url(self, connector: "ChatConnector", file_path: str) -> str:
        """Формирует URL для скачивания файла."""
        token = f"bot{connector.access_token}"
        base_url = connector.connector_url or self.BASE_API_URL
        return f"{base_url}/file/{token}/{file_path}"

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """
        Для Telegram токен не требует обновления.
        Просто возвращаем существующий access_token.
        """
        return connector.access_token

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Установить webhook URL для получения обновлений.

        Telegram API: setWebhook
        https://core.telegram.org/bots/api#setwebhook
        """
        url = self._get_api_url(connector, "setWebhook")

        payload = {
            "url": connector.webhook_url,
            "allowed_updates": json.dumps(["message"]),
            "drop_pending_updates": True,
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, data=payload)
            result = response.json()

            if not result.get("ok"):
                error_msg = result.get(
                    "description", "Unknown error setting webhook"
                )
                logger.error(f"Telegram setWebhook error: {error_msg}")
                raise ValueError(f"Telegram API error: {error_msg}")

            logger.info(
                f"Telegram webhook set successfully for connector {connector.id}"
            )
            return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """
        Удалить webhook.

        Telegram API: deleteWebhook
        https://core.telegram.org/bots/api#deletewebhook
        """
        url = self._get_api_url(connector, "deleteWebhook")

        payload = {"drop_pending_updates": True}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, data=payload)
            result = response.json()

            if not result.get("ok"):
                error_msg = result.get(
                    "description", "Unknown error deleting webhook"
                )
                logger.error(f"Telegram deleteWebhook error: {error_msg}")
                raise ValueError(f"Telegram API error: {error_msg}")

            logger.info(
                f"Telegram webhook deleted for connector {connector.id}"
            )
            return result

    async def get_webhook_info(self, connector: "ChatConnector") -> dict:
        """
        Получить информацию о текущем webhook.

        Telegram API: getWebhookInfo
        https://core.telegram.org/bots/api#getwebhookinfo
        """
        url = self._get_api_url(connector, "getWebhookInfo")

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url)
            result = response.json()

            if not result.get("ok"):
                error_msg = result.get(
                    "description", "Unknown error getting webhook info"
                )
                raise ValueError(f"Telegram API error: {error_msg}")

            return result.get("result", {})

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить текстовое сообщение в Telegram.

        Telegram API: sendMessage
        https://core.telegram.org/bots/api#sendmessage

        Args:
            connector: Коннектор Telegram
            user_from: Аккаунт отправителя (не используется для Telegram)
            body: Текст сообщения (1-4096 символов)
            chat_id: ID чата Telegram
            recipients_ids: Не используется

        Returns:
            Tuple[message_id, chat_id]
        """
        if not chat_id:
            raise ValueError("Cannot send Telegram message without chat_id")

        url = self._get_api_url(connector, "sendMessage")

        # Удаляем HTML теги из текста
        clean_text = re.sub(r"<[^>]+>", "", body)

        payload = {
            "chat_id": str(chat_id),
            "text": clean_text,
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, data=payload)
            result = response.json()

            if not result.get("ok"):
                error_msg = result.get(
                    "description", "Unknown error sending message"
                )
                logger.error(f"Telegram sendMessage error: {error_msg}")
                raise ValueError(f"Telegram API error: {error_msg}")

            message_data = result.get("result", {})
            message_id = str(message_data.get("message_id", ""))

            logger.info(
                f"Telegram message sent: {message_id} to chat {chat_id}"
            )

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
        Отправить изображение или документ в Telegram.

        Telegram API: sendPhoto / sendDocument
        https://core.telegram.org/bots/api#sendphoto
        https://core.telegram.org/bots/api#senddocument
        """
        if not chat_id:
            raise ValueError("Cannot send Telegram file without chat_id")

        # Определяем метод в зависимости от типа файла
        mimetype = attachment.mimetype or ""

        if mimetype.startswith("image/"):
            method = "sendPhoto"
            file_field = "photo"
        else:
            method = "sendDocument"
            file_field = "document"

        url = self._get_api_url(connector, method)

        # Получаем содержимое файла
        file_content = attachment.content
        file_name = attachment.name

        if file_content is None:
            raise ValueError("Attachment has no content")

        # Формируем multipart data
        files = {
            file_field: (file_name, file_content, mimetype),
        }
        data = {"chat_id": str(chat_id)}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, data=data, files=files)
            result = response.json()

            if not result.get("ok"):
                error_msg = result.get(
                    "description", "Unknown error sending file"
                )
                logger.error(f"Telegram {method} error: {error_msg}")
                raise ValueError(f"Telegram API error: {error_msg}")

            message_data = result.get("result", {})
            message_id = str(message_data.get("message_id", ""))

            logger.info(f"Telegram file sent: {message_id} to chat {chat_id}")

            return message_id, str(chat_id)

    async def get_file_path(
        self, connector: "ChatConnector", file_id: str
    ) -> str:
        """
        Получить путь к файлу по его ID.

        Telegram требует сначала получить путь к файлу,
        прежде чем его можно будет скачать.

        Telegram API: getFile
        https://core.telegram.org/bots/api#getfile
        """
        url = self._get_api_url(connector, "getFile")

        params = {"file_id": file_id}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url, params=params)
            result = response.json()

            if not result.get("ok"):
                error_msg = result.get(
                    "description", "Unknown error getting file"
                )
                raise ValueError(f"Telegram API error: {error_msg}")

            return result.get("result", {}).get("file_path", "")

    async def file_download(
        self, connector: "ChatConnector", file_info: dict | str
    ) -> bytes:
        """
        Скачать файл из Telegram.

        Args:
            connector: Коннектор
            file_info: Словарь с file_id или строка file_id

        Returns:
            Содержимое файла в байтах
        """
        # Определяем file_id
        if isinstance(file_info, dict):
            file_id = file_info.get("file_id", "")
        else:
            file_id = file_info

        # Получаем путь к файлу
        file_path = await self.get_file_path(connector, file_id)

        if not file_path:
            raise ValueError(f"Could not get file path for {file_id}")

        # Скачиваем файл
        download_url = self._get_file_url(connector, file_path)

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(download_url)

            if response.status_code != 200:
                raise ValueError(
                    f"Failed to download file: HTTP {response.status_code}"
                )
            return response.content

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> TelegramMessageAdapter:
        """Создать адаптер для сообщения Telegram."""
        return TelegramMessageAdapter(connector, raw_message)
