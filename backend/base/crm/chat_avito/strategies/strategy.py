# Copyright 2025 FARA CRM
# Chat module - Avito strategy

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Tuple

import httpx

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
from .adapter import AvitoMessageAdapter

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)


class AvitoStrategy(ChatStrategyBase):
    """
    Стратегия для интеграции с Avito Messenger API.

    Поддерживает:
    - Приём сообщений через webhook
    - Отправку текстовых сообщений
    - Отправку изображений
    - Скачивание файлов

    Требует настройки коннектора:
    - client_app_id: Client ID приложения Avito
    - client_secret: Client Secret приложения Avito
    - connector_url: https://api.avito.ru/messenger/ (по умолчанию)
    - webhook_url: URL для приёма webhook
    - access_token: генерируется автоматически
    - access_token_expired: время истечения токена
    - external_account_id: ID аккаунта Avito (опционально)

    Документация API: https://developers.avito.ru/api-catalog/messenger/documentation
    """

    strategy_type = "avito"
    BASE_API_URL = "https://api.avito.ru"
    MESSENGER_URL = "https://api.avito.ru/messenger/"
    TOKEN_URL = "https://api.avito.ru/token/"
    TIMEOUT = 30.0

    async def get_or_generate_token(self, connector: "ChatConnector") -> str:
        """
        Получить существующий access token или сгенерировать новый.

        Avito токены живут ~24 часа. При истечении генерируем новый
        через client_credentials grant.
        """
        # Проверяем срок действия текущего токена
        if connector.access_token and connector.access_token_expired:
            if connector.access_token_expired > datetime.now(timezone.utc):
                return f"{connector.access_token_type or 'Bearer'} {connector.access_token}"

        # Генерируем новый токен
        token, token_type = await self._generate_access_token(connector)
        return f"{token_type} {token}"

    async def _generate_access_token(
        self, connector: "ChatConnector"
    ) -> Tuple[str, str]:
        """
        Получить новый access token через client_credentials.

        Response:
        {
            "access_token": "...",
            "token_type": "Bearer",
            "expires_in": 86400
        }
        """
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": connector.client_app_id,
            "client_secret": connector.client_secret,
        }

        start = datetime.now(timezone.utc)

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                self.TOKEN_URL, headers=headers, data=data
            )
            result = response.json()

        access_token = result.get("access_token")
        token_type = result.get("token_type", "Bearer")
        expires_in = result.get("expires_in", 86400)

        if not access_token:
            error = result.get("error_description", result)
            raise ValueError(f"Failed to generate Avito token: {error}")

        # Обновляем коннектор (через env в реальном использовании)
        connector.access_token = access_token
        connector.access_token_type = token_type
        connector.access_token_expired = start + timedelta(seconds=expires_in)

        logger.info(
            f"Generated new Avito access token for connector {connector.id}"
        )

        return access_token, token_type

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Установить webhook URL для получения сообщений.

        После регистрации URL убедитесь что он:
        - Доступен извне
        - Возвращает 200 OK
        - Отвечает за timeout 2s

        API: POST /v3/webhook
        """
        url = f"{connector.connector_url or self.MESSENGER_URL}v3/webhook"

        token = await self.get_or_generate_token(connector)
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

        payload = {"url": connector.webhook_url}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise ValueError(
                    f"Avito setWebhook failed: {response.status_code} {response.text}"
                )

            result = response.json()
            if not result.get("ok"):
                raise ValueError(f"Avito setWebhook error: {result}")

            logger.info(
                f"Avito webhook set successfully for connector {connector.id}"
            )
            return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """
        Удалить webhook.

        API: POST /v1/webhook/unsubscribe
        """
        url = f"{connector.connector_url or self.MESSENGER_URL}v1/webhook/unsubscribe"

        token = await self.get_or_generate_token(connector)
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

        payload = {"url": connector.webhook_url}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise ValueError(
                    f"Avito unsetWebhook failed: {response.status_code} {response.text}"
                )

            result = response.json()
            logger.info(f"Avito webhook removed for connector {connector.id}")
            return result

    async def get_webhook_info(self, connector: "ChatConnector") -> dict:
        """
        Получить список подписок.

        API: POST /v1/subscriptions
        """
        url = (
            f"{connector.connector_url or self.MESSENGER_URL}v1/subscriptions"
        )

        token = await self.get_or_generate_token(connector)
        headers = {"Authorization": token}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, headers=headers)
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

        API: POST /v1/accounts/{user_id}/chats/{chat_id}/messages

        Args:
            connector: Коннектор Avito
            user_from: Аккаунт отправителя (external_account)
            body: Текст сообщения
            chat_id: ID чата в Avito
            recipients_ids: Не используется

        Returns:
            Tuple[message_id, chat_id]
        """
        if not chat_id:
            raise ValueError("Cannot send Avito message without chat_id")

        # user_from.external_id содержит ID аккаунта Avito
        user_id = user_from.external_id

        url = (
            f"{connector.connector_url or self.MESSENGER_URL}"
            f"v1/accounts/{user_id}/chats/{chat_id}/messages"
        )

        token = await self.get_or_generate_token(connector)
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

        # Удаляем HTML теги
        clean_text = re.sub(r"<[^>]+>", "", body)

        payload = {
            "message": {"text": clean_text},
            "type": "text",
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise ValueError(
                    f"Avito sendMessage failed: {response.status_code} {response.text}"
                )

            result = response.json()
            message_id = str(result.get("id", ""))

            logger.info(f"Avito message sent: {message_id} to chat {chat_id}")

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
        Отправить изображение.

        Avito поддерживает только изображения (JPEG, HEIC, GIF, BMP, PNG).
        Максимальный размер: 24 МБ
        Максимальное разрешение: 75 мегапикселей

        Процесс:
        1. Загружаем изображение через uploadImages
        2. Отправляем сообщение с image_id

        Args:
            connector: Коннектор Avito
            user_from: Аккаунт отправителя
            chat_id: ID чата
            attachment: Вложение для отправки

        Returns:
            Tuple[message_id, chat_id]
        """
        if not chat_id:
            raise ValueError("Cannot send Avito file without chat_id")

        user_id = user_from.external_id

        # Шаг 1: Загружаем изображение
        image_id = await self._upload_image(connector, user_id, attachment)

        # Шаг 2: Отправляем сообщение с изображением
        url = (
            f"{connector.connector_url or self.MESSENGER_URL}"
            f"v1/accounts/{user_id}/chats/{chat_id}/messages/image"
        )

        token = await self.get_or_generate_token(connector)
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

        payload = {"image_id": image_id}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise ValueError(
                    f"Avito sendImage failed: {response.status_code} {response.text}"
                )

            result = response.json()
            message_id = str(result.get("id", ""))

            logger.info(f"Avito image sent: {message_id} to chat {chat_id}")

            return message_id, str(chat_id)

    async def _upload_image(
        self,
        connector: "ChatConnector",
        user_id: str,
        attachment: "Attachment",
    ) -> str:
        """
        Загрузить изображение в Avito.

        API: POST /v1/accounts/{user_id}/uploadImages

        Returns:
            image_id для использования в sendImage
        """
        url = (
            f"{connector.connector_url or self.MESSENGER_URL}"
            f"v1/accounts/{user_id}/uploadImages"
        )

        token = await self.get_or_generate_token(connector)
        headers = {"Authorization": token}

        attachment.content = await attachment.read_content()
        # Формируем multipart данные
        files = {
            "uploadfile[]": (
                attachment.name,
                attachment.content,
                attachment.mimetype or "image/jpeg",
            )
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(url, headers=headers, files=files)

            if response.status_code != 200:
                raise ValueError(
                    f"Avito uploadImage failed: {response.status_code} {response.text}"
                )

            result = response.json()

            # Avito возвращает словарь где ключ = image_id
            # {
            #     "44540672315.96c51d74166f41d8b6cca4dbcaabf245": {
            #         "1280x960": "https://...",
            #         ...
            #     }
            # }
            for image_id in result.keys():
                return image_id

            raise ValueError("No image_id in Avito uploadImage response")

    async def file_download(
        self, connector: "ChatConnector", file_url: str | dict
    ) -> bytes:
        """
        Скачать файл из Avito.

        Avito предоставляет готовые URL для скачивания.

        Args:
            connector: Коннектор
            file_url: URL файла (строка или словарь с URL)

        Returns:
            Содержимое файла в байтах
        """
        url = file_url if isinstance(file_url, str) else str(file_url)

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url)

            if response.status_code != 200:
                raise ValueError(
                    f"Failed to download Avito file: HTTP {response.status_code}"
                )

            return response.content

    async def get_partner_name(
        self,
        connector: "ChatConnector",
        user_id: str,
        chat_id: str | None = None,
    ) -> str | None:
        """
        Получить имя клиента из чата.

        API: GET /v2/accounts/{user_id}/chats/{chat_id}
        """
        if not chat_id:
            return None

        url = (
            f"{connector.connector_url or self.MESSENGER_URL}"
            f"v2/accounts/{user_id}/chats/{chat_id}"
        )

        token = await self.get_or_generate_token(connector)
        headers = {"Authorization": token}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                result = response.json()
                users = result.get("users", [])
                if users:
                    return users[0].get("name")

            return None

    async def get_self_account_id(self, connector: "ChatConnector") -> dict:
        """
        Получить информацию об аккаунте.

        API: GET /core/v1/accounts/self
        """
        url = f"{self.BASE_API_URL}/core/v1/accounts/self"

        token = await self.get_or_generate_token(connector)
        headers = {"Authorization": token}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                return response.json()

            raise ValueError(
                f"Avito get_self_account_id failed: {response.status_code} {response.text}"
            )

    async def get_item_url(
        self, connector: "ChatConnector", user_id: str, item_id: str
    ) -> str | None:
        """
        Получить URL объявления по его ID.

        API: GET /core/v1/accounts/{user_id}/items/{item_id}
        """
        url = f"{self.BASE_API_URL}/core/v1/accounts/{user_id}/items/{item_id}"

        token = await self.get_or_generate_token(connector)
        headers = {"Authorization": token}

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                return response.json().get("url")

            return None

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> AvitoMessageAdapter:
        """Создать адаптер для сообщения Avito."""
        return AvitoMessageAdapter(connector, raw_message)
