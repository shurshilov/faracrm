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
    from backend.project_setup import ChatConnector
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.attachments.models.attachments import Attachment
    from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter

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
            "Generated new Avito access token for connector %s", connector.id
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
                "Avito webhook set successfully for connector %s", connector.id
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
            logger.info("Avito webhook removed for connector %s", connector.id)
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
        thread_message_id: str | None = None,
        attachments: list | None = None,
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
        # user_id = user_from.external_id
        # TODO: подумать над рефакторингом
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

            logger.info(
                "Avito message sent: %s to chat %s", message_id, chat_id
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

            logger.info("Avito image sent: %s to chat %s", message_id, chat_id)

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

    # async def file_download(
    #     self, connector: "ChatConnector", file_url: str | dict
    # ) -> bytes:
    #     """
    #     Скачать файл из Avito.

    #     Avito предоставляет готовые URL для скачивания.

    #     Args:
    #         connector: Коннектор
    #         file_url: URL файла (строка или словарь с URL)

    #     Returns:
    #         Содержимое файла в байтах
    #     """
    #     url = file_url if isinstance(file_url, str) else str(file_url)

    #     async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
    #         response = await client.get(url)

    #         if response.status_code != 200:
    #             raise ValueError(
    #                 f"Failed to download Avito file: HTTP {response.status_code}"
    #             )

    #         return response.content

    async def _get_chat_info(
        self,
        connector: "ChatConnector",
        user_id: str,
        chat_id: str | None = None,
    ):
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
                return result
            return None

    def _counterparty_user(
        self, connector: "ChatConnector", info: dict | None
    ):
        """Из info чата вернуть участника, отличного от нашего аккаунта.

        В Avito массив users содержит обоих участников (нас и клиента).
        Клиент — тот, чей id не равен нашему external_account_id.
        """
        if not info:
            return {}
        me = str(connector.external_account_id or "")
        for user in info.get("users") or []:
            if str(user.get("id")) != me:
                return user
        return {}

    async def get_item_title(
        self, connector: "ChatConnector", user_id, item_id, chat_id=None
    ):
        """Получение заголовка объявления.

        В вебхуке Avito заголовка нет — поэтому идём за ним через
        v2/accounts/{user_id}/chats/{chat_id}, который возвращает
        context.value.title (см. swagger).
        """
        if not chat_id or not user_id:
            return ""
        info = await self._get_chat_info(connector, user_id, chat_id) or {}
        ctx_value = (info.get("context") or {}).get("value") or {}
        return ctx_value.get("title") or ""

    async def get_item_info(
        self, connector: "ChatConnector", user_id, item_id, chat_id=None
    ):
        """Один HTTP-вызов — получаем и заголовок, и url объявления.

        В Avito эндпоинт чата возвращает оба поля сразу
        (context.value.title и context.value.url), что экономит запросы.
        """
        if not chat_id or not user_id:
            return {"title": "", "url": ""}
        info = await self._get_chat_info(connector, user_id, chat_id) or {}
        ctx_value = (info.get("context") or {}).get("value") or {}
        return {
            "title": ctx_value.get("title") or "",
            "url": ctx_value.get("url") or "",
        }

    # async def get_partner_name(
    #     self,
    #     connector: "ChatConnector",
    #     user_id: str,
    #     chat_id: str | None = None,
    # ) -> str | None:
    #     """
    #     Получить имя клиента из чата.

    #     API: GET /v2/accounts/{user_id}/chats/{chat_id}
    #     """
    #     if not chat_id:
    #         return None

    #     url = (
    #         f"{connector.connector_url or self.MESSENGER_URL}"
    #         f"v2/accounts/{user_id}/chats/{chat_id}"
    #     )

    #     token = await self.get_or_generate_token(connector)
    #     headers = {"Authorization": token}

    #     async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
    #         response = await client.get(url, headers=headers)

    #         if response.status_code == 200:
    #             result = response.json()
    #             # users содержит обоих участников — берём клиента (не нас).
    #             other = self._counterparty_user(connector, result)
    #             if other:
    #                 return other.get("name")

    #         return None

    async def resolve_partner_id_and_name(
        self,
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> tuple[str | None, str | None]:
        """Определить клиента чата за один запрос: (external_id, name).

        Avito не присылает имя клиента в webhook и не отличает «нас» от клиента
        в author_id, поэтому участников берём из чата (v2/.../chats/{chat_id}) —
        это даёт и имя, и id «другого» участника (того, кто не наш аккаунт).

        - Пишет клиент (author != наш аккаунт): id = author_id; имя — из чата.
        - Пишем мы (author == наш аккаунт): id и имя берём из участника чата.
        - Клиента определить не удалось → (None, None): сообщение пропускается,
          чтобы не завести партнёра/лид на наш аккаунт.
        """
        author = adapter.author_id

        # Участники чата (имя в webhook не приходит; отсюда же id клиента,
        # когда писали мы сами).
        other = {}
        try:
            # self.connector.external_account_id
            info = await self._get_chat_info(
                connector, adapter.user_id, adapter.chat_id
            )
            other = self._counterparty_user(connector, info)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Avito: failed to fetch chat %s participants: %s",
                adapter.chat_id,
                exc,
            )

        # id клиента.
        if adapter.is_from_external:
            client_id = author
        else:
            logger.warning(
                "Avito: outgoing message %s in chat %s — cannot resolve "
                "client from chat participants; skipping",
                adapter.message_id,
                adapter.chat_id,
            )
            return None, None

        name = other.get("name", client_id)
        return client_id, name

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
