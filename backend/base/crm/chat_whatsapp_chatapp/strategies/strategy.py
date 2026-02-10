# Copyright 2025 FARA CRM
# Chat module - WhatsApp ChatApp strategy

import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Tuple

import httpx

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
from .adapter import WhatsAppChatAppMessageAdapter

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)


class WhatsAppChatAppStrategy(ChatStrategyBase):
    """
    Стратегия для интеграции с WhatsApp через ChatApp API.

    ChatApp (https://chatapp.online) - сервис для работы с WhatsApp Business API.

    Поддерживает:
    - Приём сообщений через webhook
    - Отправку текстовых сообщений
    - Отправку файлов и изображений
    - Скачивание файлов

    Требует настройки коннектора:
    - email: Email аккаунта ChatApp
    - password: Пароль аккаунта
    - client_app_id: App ID приложения ChatApp
    - license_id: ID лицензии WhatsApp
    - connector_url: https://api.chatapp.online/v1/ (по умолчанию)
    - webhook_url: URL для приёма webhook
    - access_token: генерируется автоматически
    - refresh_token: для обновления access_token
    - access_token_expired: время истечения токена

    Документация API: https://api.chatapp.online/docs
    """

    strategy_type = "whatsapp_chatapp"
    BASE_API_URL = "https://api.chatapp.online/v1/"
    MESSENGER_TYPE = "grWhatsApp"
    TIMEOUT = 30.0

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """
        Получить существующий access token или сгенерировать новый.

        ChatApp токены:
        - accessToken: живёт 24 часа
        - refreshToken: живёт 14 дней

        Лимит: 100 токенов в день на email-appId.
        """
        # Проверяем срок действия текущего токена
        if connector.access_token and connector.access_token_expired:
            if connector.access_token_expired > datetime.now(timezone.utc):
                return connector.access_token

        # Генерируем новый токен
        access_token, _ = await self._generate_access_token(connector)
        return access_token

    async def _generate_access_token(
        self, connector: "ChatConnector"
    ) -> Tuple[str, str]:
        """
        Получить новый access token через email/password.

        API: POST /tokens

        Response:
        {
            "success": true,
            "data": {
                "accessToken": "...",
                "refreshToken": "...",
                "accessTokenEndTime": 1752478933,
                "refreshTokenEndTime": 1753602533
            }
        }
        """
        url = f"{connector.connector_url or self.BASE_API_URL}tokens"

        headers = {"Content-Type": "application/json"}
        params = {
            "email": connector.email,
            "password": connector.password,
            "appId": connector.client_app_id,
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, headers=headers, params=params)
            result = response.json()

        if not result.get("success"):
            error = result.get("message", result)
            raise ValueError(f"Failed to generate ChatApp token: {error}")

        data = result.get("data", {})
        access_token = data.get("accessToken")
        refresh_token = data.get("refreshToken")
        access_token_end = data.get("accessTokenEndTime", 0)
        refresh_token_end = data.get("refreshTokenEndTime", 0)

        if not access_token:
            raise ValueError("No accessToken in ChatApp response")

        # Обновляем коннектор
        connector.access_token = access_token
        connector.refresh_token = refresh_token
        connector.access_token_expired = datetime.fromtimestamp(
            access_token_end, tz=timezone.utc
        )
        connector.refresh_token_expired = datetime.fromtimestamp(
            refresh_token_end, tz=timezone.utc
        )

        logger.info(
            "Generated new ChatApp access token for connector %s", connector.id
        )

        return access_token, refresh_token

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Установить webhook URL для получения сообщений.

        API: PUT /licenses/{licenseId}/messengers/{messengerType}/callbackUrl

        Events:
        - message (incoming/outgoing message)
        - messageStatus (sent message status)
        - и другие...

        URL должен отвечать 200 на пустой POST запрос.
        """
        url = (
            f"{connector.connector_url or self.BASE_API_URL}"
            f"licenses/{connector.license_id}/messengers/{self.MESSENGER_TYPE}/callbackUrl"
        )

        token = await self.get_or_generate_token(connector)
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

        payload = {
            "events": ["message"],
            "url": connector.webhook_url,
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.put(url, headers=headers, json=payload)
            result = response.json()

            if not result.get("success"):
                raise ValueError(f"ChatApp setWebhook error: {result}")

            logger.info(
                "ChatApp webhook set successfully for connector %s",
                connector.id,
            )
            return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """
        Удалить webhook.

        API: DELETE /licenses/{licenseId}/messengers/{messengerType}/callbackUrl
        """
        url = (
            f"{connector.connector_url or self.BASE_API_URL}"
            f"licenses/{connector.license_id}/messengers/{self.MESSENGER_TYPE}/callbackUrl"
        )

        token = await self.get_or_generate_token(connector)
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.delete(url, headers=headers)
            result = response.json()

            if not result.get("success"):
                raise ValueError(f"ChatApp unsetWebhook error: {result}")

            logger.info(
                "ChatApp webhook removed for connector %s", connector.id
            )
            return result

    async def get_webhook_info(self, connector: "ChatConnector") -> dict:
        """
        Получить список callback URLs.

        API: GET /callbackUrls
        """
        url = f"{connector.connector_url or self.BASE_API_URL}callbackUrls"

        token = await self.get_or_generate_token(connector)
        headers = {"Authorization": token}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url, headers=headers)
            return response.json()

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить текстовое сообщение.

        API: POST /licenses/{licenseId}/messengers/{messengerType}/chats/{chatId}/messages/text

        Args:
            connector: Коннектор ChatApp
            user_from: Аккаунт отправителя
            body: Текст сообщения
            chat_id: ID чата (формат: phone@c.us)
            recipients_ids: Список получателей (если нет chat_id)

        Returns:
            Tuple[message_id, chat_id]
        """
        # Если нет chat_id, используем телефон получателя
        if not chat_id:
            if not recipients_ids:
                raise ValueError(
                    "Cannot send message: no chat_id or recipients"
                )
            chat_id = recipients_ids[0].external_id

        url = (
            f"{connector.connector_url or self.BASE_API_URL}"
            f"licenses/{connector.license_id}/messengers/{self.MESSENGER_TYPE}/"
            f"chats/{chat_id}/messages/text"
        )

        token = await self.get_or_generate_token(connector)
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

        # Удаляем HTML теги
        clean_text = re.sub(r"<[^>]+>", "", body)

        payload = {"text": clean_text}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)
            result = response.json()

            if not result.get("success"):
                raise ValueError(f"ChatApp sendMessage error: {result}")

            data = result.get("data", {})
            message_id = str(data.get("id", ""))
            returned_chat_id = str(data.get("chatId", chat_id))

            logger.info(
                "ChatApp message sent: %s to chat %s",
                message_id,
                returned_chat_id,
            )

            return message_id, returned_chat_id

    async def chat_send_message_binary(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        chat_id: str,
        attachment: "Attachment",
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить файл или изображение.

        API: POST /licenses/{licenseId}/messengers/{messengerType}/chats/{chatId}/messages/file

        Поддерживает multipart/form-data с полями:
        - file: содержимое файла
        - fileName: имя файла
        - caption: подпись (опционально)

        Args:
            connector: Коннектор ChatApp
            user_from: Аккаунт отправителя
            chat_id: ID чата
            attachment: Вложение для отправки

        Returns:
            Tuple[message_id, chat_id]
        """
        if not chat_id:
            if not recipients_ids:
                raise ValueError("Cannot send file: no chat_id or recipients")
            chat_id = recipients_ids[0].external_id

        url = (
            f"{connector.connector_url or self.BASE_API_URL}"
            f"licenses/{connector.license_id}/messengers/{self.MESSENGER_TYPE}/"
            f"chats/{chat_id}/messages/file"
        )

        token = await self.get_or_generate_token(connector)
        headers = {"Authorization": token}

        attachment.content = await attachment.read_content()
        # Формируем multipart данные
        files = {
            "fileName": (None, attachment.name),
            "file": (
                attachment.name,
                attachment.content,
                attachment.mimetype or "application/octet-stream",
            ),
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, headers=headers, files=files)
            result = response.json()

            if not result.get("success"):
                raise ValueError(f"ChatApp sendFile error: {result}")

            data = result.get("data", {})
            message_id = str(data.get("id", ""))

            logger.info(
                "ChatApp file sent: %s to chat %s", message_id, chat_id
            )

            return message_id, str(chat_id)

    async def file_download(
        self, connector: "ChatConnector", file_info: dict | str
    ) -> bytes:
        """
        Скачать файл.

        ChatApp предоставляет готовые публичные URL в message.file.link.

        Args:
            connector: Коннектор
            file_info: Словарь с link или строка URL

        Returns:
            Содержимое файла в байтах
        """
        if isinstance(file_info, dict):
            url = file_info.get("link", "")
        else:
            url = str(file_info)

        if not url:
            raise ValueError("No URL provided for file download")

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url)

            if response.status_code != 200:
                raise ValueError(
                    f"Failed to download file: HTTP {response.status_code}"
                )

            return response.content

    async def get_licenses(self, connector: "ChatConnector") -> dict:
        """
        Получить список лицензий.

        API: GET /licenses
        """
        url = f"{connector.connector_url or self.BASE_API_URL}licenses"

        token = await self.get_or_generate_token(connector)
        headers = {"Authorization": token}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                return response.json()

            raise ValueError(
                f"ChatApp get_licenses failed: {response.status_code} {response.text}"
            )

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> WhatsAppChatAppMessageAdapter:
        """Создать адаптер для сообщения ChatApp."""
        return WhatsAppChatAppMessageAdapter(connector, raw_message)
