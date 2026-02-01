# Copyright 2025 FARA CRM
# Chat module - base strategy pattern

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Tuple
import json
import logging

from backend.base.crm.users.models.users import User

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.partners.models.contact import Contact
    from backend.base.crm.attachments.models.attachments import Attachment
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter

logger = logging.getLogger(__name__)


class ChatStrategyBase(ABC):
    """
    Базовый класс стратегии для работы с внешними сервисами.

    Реализует паттерн Strategy для легкого добавления новых провайдеров
    (Telegram, WhatsApp, Avito и т.д.) без изменения основного кода.

    Каждый провайдер реализует свой класс стратегии, наследуя от этого.

    Шаблонный метод handle_webhook содержит общую логику обработки
    входящих сообщений. Конкретные стратегии переопределяют только
    create_message_adapter для парсинга специфичного формата.
    """

    # Уникальный тип стратегии (должен совпадать с connector.type)
    strategy_type: str = ""

    # ========================================================================
    # Абстрактные методы - должны быть реализованы в каждой стратегии
    # ========================================================================

    @abstractmethod
    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """
        Получить существующий access token или сгенерировать новый.

        Должен проверить срок действия текущего токена и при необходимости
        использовать refresh_token для получения нового.

        Args:
            connector: Экземпляр коннектора

        Returns:
            Access token или None если не удалось получить
        """
        pass

    @abstractmethod
    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Установить webhook URL для получения сообщений от провайдера.

        Args:
            connector: Экземпляр коннектора

        Returns:
            True если успешно, иначе выбрасывает исключение
        """
        pass

    @abstractmethod
    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """
        Удалить webhook.

        Args:
            connector: Экземпляр коннектора

        Returns:
            Ответ от API провайдера
        """
        pass

    @abstractmethod
    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "Contact",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить текстовое сообщение.

        Args:
            connector: Экземпляр коннектора
            user_from: Контакт отправителя
            body: Текст сообщения
            chat_id: ID внешнего чата (если известен)
            recipients_ids: Список получателей (если нет chat_id)

        Returns:
            Tuple[external_message_id, external_chat_id]
        """
        pass

    # async def chat_send_file(
    #     self,
    #     connector: "ChatConnector",
    #     user_from: "ChatExternalAccount",
    #     chat_id: str,
    #     file_content: bytes,
    #     filename: str,
    #     mimetype: str,
    #     caption: str | None = None,
    # ) -> str | None:
    #     """
    #     Отправить файл/изображение.

    #     Args:
    #         connector: Экземпляр коннектора
    #         user_from: Аккаунт отправителя
    #         chat_id: ID внешнего чата
    #         file_content: Содержимое файла в байтах
    #         filename: Имя файла
    #         mimetype: MIME-тип файла
    #         caption: Подпись к файлу (опционально)

    #     Returns:
    #         external_message_id или None
    #     """
    #     # По умолчанию не поддерживается - стратегии переопределяют
    #     logger.warning(
    #         f"[{self.strategy_type}] chat_send_file not implemented"
    #     )
    #     return None

    @abstractmethod
    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> "ChatMessageAdapter":
        """
        Создать адаптер для парсинга сырого сообщения от провайдера.

        Каждая стратегия реализует свой адаптер для преобразования
        специфичного формата сообщения в унифицированный.

        Args:
            connector: Экземпляр коннектора
            raw_message: Сырые данные сообщения

        Returns:
            Адаптер сообщения
        """
        pass

    # ========================================================================
    # Webhook обработка - шаблонный метод с общей логикой
    # ========================================================================

    async def handle_webhook(
        self,
        connector: "ChatConnector",
        payload: dict,
        env: "Environment",
    ) -> dict:
        """
        Шаблонный метод обработки входящего webhook запроса.

        Содержит общую логику:
        1. Создание адаптера сообщения
        2. Проверка на пропуск
        3. Проверка дубликатов
        4. Обработка сообщения
        5. Отправка в WebSocket

        Конкретные стратегии могут переопределить для особой логики,
        но обычно достаточно реализовать create_message_adapter.

        Args:
            connector: Экземпляр коннектора
            payload: Данные от провайдера
            env: Environment с доступом к моделям

        Returns:
            Ответ для провайдера
        """
        try:
            # 1. Создаём адаптер сообщения
            adapter = self.create_message_adapter(connector, payload)

            # 2. Проверяем нужно ли пропустить
            if adapter.should_skip:
                logger.info(
                    f"[{self.strategy_type}] Skipping message {adapter.message_id}"
                )
                return {"ok": True}

            # 3. Проверяем дубликат
            if await self._is_duplicate_message(env, connector, adapter):
                logger.info(
                    f"[{self.strategy_type}] Duplicate message {adapter.message_id}"
                )
                return {"ok": True}

            # 4. Обрабатываем сообщение в транзакции
            async with env.apps.db.get_transaction():
                await self._process_incoming_message(env, connector, adapter)

            return {"ok": True}

        except NotImplementedError as e:
            logger.warning(f"[{self.strategy_type}] Not implemented: {e}")
            return {"ok": True}
        except Exception as e:
            logger.error(
                f"[{self.strategy_type}] Error processing webhook: {e}",
                exc_info=True,
            )
            # Возвращаем OK чтобы провайдер не повторял запрос
            return {"ok": True}

    async def _is_duplicate_message(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> bool:
        """Проверить является ли сообщение дубликатом."""
        return await env.models.chat_external_message.exists(
            external_id=adapter.message_id,
            connector_id=connector.id,
        )

    async def _process_incoming_message(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> None:
        """
        Обработать входящее сообщение от внешнего сервиса.

        1. Найти или создать внешний аккаунт отправителя
        2. Найти или создать внутренний чат
        3. Создать сообщение
        4. Создать связь с внешним сообщением
        5. Обработать вложения
        6. Отправить через WebSocket
        """
        from backend.base.crm.chat.websocket import chat_manager

        # 1. Найти или создать ExternalAccount + Contact
        external_account, contact, created = (
            await env.models.chat_external_account.find_or_create_for_webhook(
                connector=connector,
                external_id=adapter.author_id,
                contact_value=adapter.author_id,  # email / phone / username
                display_name=adapter.author_name,
                raw=json.dumps(adapter.raw) if adapter.raw else None,
            )
        )

        # 2. Найти или создать связь с внешним чатом
        external_chat = (
            await env.models.chat_external_chat.find_by_external_id(
                external_id=adapter.chat_id,
                connector_id=connector.id,
            )
        )

        if external_chat and external_chat.chat_id:
            # Используем существующий внутренний чат
            chat_id = external_chat.chat_id.id
        else:
            # Создаём новый внутренний чат и внешний чат
            chat_id = await self._create_new_chat(
                env, connector, adapter, external_account
            )
            if chat_id is None:
                return

        # 3. Определяем автора сообщения через contact
        # Если это оператор (есть user_id) - автор user
        # Если это клиент (есть partner_id) - автор partner
        author_user_id = None
        author_partner_id = None

        if contact.user_id:
            # Оператор
            author_user_id = contact.user_id.id
        elif contact.partner_id:
            # Клиент
            author_partner_id = contact.partner_id.id

        # 4. Создаём сообщение
        # Для email коннектора используем message_type="email"
        message_type = "email" if connector.type == "email" else "comment"

        message = await env.models.chat_message.post_message(
            chat_id=chat_id,
            author_user_id=author_user_id,
            author_partner_id=author_partner_id,
            body=adapter.text or "",
            message_type=message_type,
            connector_id=connector.id,
        )

        # 5. Создаём связь с внешним сообщением
        await env.models.chat_external_message.create_link(
            external_id=adapter.message_id,
            connector_id=connector.id,
            message_id=message.id,
            external_chat_id=adapter.chat_id,
        )

        # 6. Обрабатываем изображения
        await self._process_attachments(connector, adapter, message)

        # 7. Отправляем уведомление через WebSocket
        author_data = {
            "id": author_user_id or author_partner_id,
            "name": adapter.author_name,
            "type": "user" if author_user_id else "partner",
        }

        await chat_manager.send_to_chat(
            chat_id=chat_id,
            message={
                "type": "new_message",
                "chat_id": chat_id,
                "message": {
                    "id": message.id,
                    "body": message.body,
                    "author": author_data,
                    "author_user_id": author_user_id,
                    "author_partner_id": author_partner_id,
                    "create_date": (
                        message.create_date.isoformat()
                        if message.create_date
                        else None
                    ),
                    "connector_type": connector.type,
                },
                "external": True,
            },
        )

        logger.info(
            f"[{self.strategy_type}] Processed message "
            f"{adapter.message_id} -> internal {message.id}"
        )

    async def _create_new_chat(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
        external_account: "ChatExternalAccount",
    ) -> int | None:
        """Создать новый чат для входящего сообщения."""
        # Находим оператора для назначения (теперь через connector)
        operator_id = await connector.get_next_operator()

        if not operator_id:
            logger.warning(
                f"[{self.strategy_type}] No operator available "
                f"for connector {connector.id}"
            )
            return None

        # Создаём чат
        # is_internal=False т.к. это внешний чат (от коннектора)
        chat_name = (
            f"{adapter.author_name or adapter.author_id} ({connector.name})"
        )

        now = datetime.now(timezone.utc)
        chat = env.models.chat(
            name=chat_name,
            chat_type="direct",
            is_internal=False,  # Внешний чат
            create_user_id=User(id=operator_id),
            create_date=now,
            write_date=now,
        )
        chat_id = await env.models.chat.create(payload=chat)

        # Добавляем оператора как участника (через ChatMember)
        chat_obj = await env.models.chat.get(chat_id)
        operator_member = env.models.chat_member(
            chat_id=chat_obj,
            user_id=User(id=operator_id),
        )
        await env.models.chat_member.create(payload=operator_member)

        # Добавляем клиента (партнёра) как участника (через contact)
        if (
            external_account.contact_id
            and external_account.contact_id.partner_id
        ):
            partner_member = env.models.chat_member(
                chat_id=chat_obj,
                partner_id=external_account.contact_id.partner_id,
            )
            await env.models.chat_member.create(payload=partner_member)

        # Создаём связь с внешним чатом и сам внешний чат
        await env.models.chat_external_chat.create_link(
            external_id=adapter.chat_id,
            connector_id=connector.id,
            chat_id=chat_id,
        )

        logger.info(
            f"[{self.strategy_type}] Created new chat {chat_id} "
            f"for external {adapter.chat_id}"
        )

        return chat_id

    async def _process_attachments(
        self,
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
        message,
    ) -> None:
        """Обработать вложения (изображения, файлы)."""
        for image_url in adapter.images:
            try:
                image_content = await self.file_download(connector, image_url)
                # TODO: Интеграция с модулем attachments
                logger.debug(
                    f"[{self.strategy_type}] Downloaded image: {len(image_content)} bytes"
                )
            except Exception as e:
                logger.error(
                    f"[{self.strategy_type}] Error downloading image: {e}"
                )

        for file_info in adapter.files:
            try:
                file_content = await self.file_download(
                    connector, file_info.get("url", "")
                )
                # TODO: Интеграция с модулем attachments
                logger.debug(
                    f"[{self.strategy_type}] Downloaded file: "
                    f"{file_info.get('name')} ({len(file_content)} bytes)"
                )
            except Exception as e:
                logger.error(
                    f"[{self.strategy_type}] Error downloading file: {e}"
                )

    # ========================================================================
    # Дополнительные методы
    # ========================================================================

    async def get_webhook_info(self, connector: "ChatConnector") -> dict:
        """
        Получить информацию о текущем webhook.

        Args:
            connector: Экземпляр коннектора

        Returns:
            Словарь с информацией о webhook
        """
        return {}

    async def chat_send_message_binary(
        self,
        connector: "ChatConnector",
        user_from: "Contact",
        chat_id: str,
        attachment: Any,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить файл или изображение.

        Args:
            connector: Экземпляр коннектора
            user_from: Контакт отправителя
            chat_id: ID внешнего чата
            attachment: Вложение для отправки
            recipients_ids: Список получателей

        Returns:
            Tuple[external_message_id, external_chat_id]
        """
        raise NotImplementedError(
            f"Binary messages not supported for {self.strategy_type}"
        )

    async def file_download(
        self, connector: "ChatConnector", file_url: str
    ) -> bytes:
        """
        Скачать файл по URL.

        Args:
            connector: Экземпляр коннектора
            file_url: URL файла

        Returns:
            Содержимое файла в байтах
        """
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(file_url)
            return response.content

    async def get_partner_name(
        self, connector: "ChatConnector", user_id: str
    ) -> str | None:
        """
        Получить имя пользователя по его ID во внешней системе.

        Args:
            connector: Экземпляр коннектора
            user_id: ID пользователя

        Returns:
            Имя пользователя или None
        """
        return None

    async def get_item_url(
        self, connector: "ChatConnector", user_id: str, item_id: str
    ) -> str | None:
        """
        Получить URL элемента (например, объявления в Avito).

        Args:
            connector: Экземпляр коннектора
            user_id: ID пользователя
            item_id: ID элемента

        Returns:
            URL элемента или None
        """
        return None

    async def send_outgoing_message(
        self,
        env: "Environment",
        chat_id: int,
        connector_id: "ChatConnector",
        user_id: int,
        body: str,
        message_id: int,
        attachments: list["Attachment"] | None = None,
        recipients_ids: list[dict] | None = None,
    ) -> bool:
        """
        Отправить сообщение во внешний коннектор (Telegram, WhatsApp и т.д.)

        Args:
            env: Environment
            chat_id: ID внутреннего чата
            connector_id: коннектор
            user_id: ID пользователя-отправителя
            body: Текст сообщения
            message_id: ID внутреннего сообщения
            attachments: Список вложений [{id, name, mimetype, size, content}]
            recipients_ids: Список контактов получателей [{"id": ..., "contact_value": ...}]

        Returns:
            True если успешно отправлено
        """
        try:
            # Находим external_chat для этого чата и коннектора
            external_chat = await env.models.chat_external_chat.search(
                filter=[
                    ("chat_id", "=", chat_id),
                    ("connector_id", "=", connector_id.id),
                ],
                fields=["id", "external_id"],
                limit=1,
            )

            external_chat_id = None

            if external_chat:
                # Есть существующий external_chat - используем его
                external_chat_id = external_chat[0].external_id
            elif recipients_ids:
                # Первое сообщение - используем контакты получателей
                # Пока поддерживаем отправку только одному получателю
                if len(recipients_ids) > 1:
                    logger.warning(
                        f"Multiple recipients not fully supported yet, using first one"
                    )

                recipient = recipients_ids[0]
                external_chat_id = recipient["contact_value"]

                # Создаём external_chat для последующих сообщений
                # await env.models.chat_external_chat.create_link(
                #     external_id=external_chat_id,
                #     connector_id=connector_id.id,
                #     chat_id=chat_id,
                # )
                # logger.info(
                #     f"Created external_chat for chat={chat_id}, "
                #     f"connector={connector_id.id}, external_id={external_chat_id}"
                # )
            else:
                logger.warning(
                    f"No external_chat found for chat={chat_id}, connector={connector_id.id} "
                    f"and no recipients provided"
                )
                return False

            # Находим контакт оператора по contact_type_id коннектора
            operator_ct_id = None
            if connector_id.contact_type_id:
                operator_ct_id = connector_id.contact_type_id.id

            if not operator_ct_id:
                operator_ct_id = await env.models.contact_type.get_contact_type_id_for_connector(
                    connector_id.type
                )

            operator_contact = await env.models.contact.search(
                filter=[
                    ("contact_type_id", "=", operator_ct_id),
                    ("user_id", "=", user_id),
                    ("active", "=", True),
                ],
                limit=1,
            )

            if not operator_contact:
                logger.warning(
                    f"No operator contact found for connector {connector_id.id}, user {user_id}"
                )
                return False

            external_msg_id = None

            # Отправляем вложения
            if attachments:
                for att in attachments:
                    try:
                        # Получаем содержимое вложения из БД
                        # attachment = await env.models.attachment.get(att["id"])
                        # if not attachment:
                        #     continue
                        file_msg_id = await self.chat_send_message_binary(
                            connector_id,
                            operator_contact[0],
                            external_chat_id,
                            att,
                        )

                        if file_msg_id and not external_msg_id:
                            external_msg_id = file_msg_id

                    except Exception as e:
                        logger.error(
                            f"Failed to send attachment {att.get('id')}: {e}"
                        )

            # Если нет вложений или есть текст без caption — отправляем текст
            if body.strip():
                text_msg_id, _ = await self.chat_send_message(
                    connector=connector_id,
                    user_from=operator_contact[0],
                    body=body,
                    chat_id=external_chat_id,
                )
                if text_msg_id:
                    external_msg_id = text_msg_id

            # Сохраняем связь с внешним сообщением
            if external_msg_id:
                await env.models.chat_external_message.create_link(
                    external_id=str(external_msg_id),
                    connector_id=connector_id.id,
                    message_id=message_id,
                    external_chat_id=external_chat_id,
                )

            logger.info(
                f"Sent message to {connector_id.type}: "
                f"internal={message_id}, external={external_msg_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to send to external connector: {e}", exc_info=True
            )
            return False
