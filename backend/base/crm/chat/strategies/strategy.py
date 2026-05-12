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

    @abstractmethod
    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Установить webhook URL для получения сообщений от провайдера.

        Args:
            connector: Экземпляр коннектора

        Returns:
            True если успешно, иначе выбрасывает исключение
        """

    @abstractmethod
    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """
        Удалить webhook.

        Args:
            connector: Экземпляр коннектора

        Returns:
            Ответ от API провайдера
        """

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
                    "[%s] Skipping message %s",
                    self.strategy_type,
                    adapter.message_id,
                )
                return {"ok": True}

            # 3. Проверяем дубликат
            if await self._is_duplicate_message(env, connector, adapter):
                logger.info(
                    "[%s] Duplicate message %s",
                    self.strategy_type,
                    adapter.message_id,
                )
                return {"ok": True}

            # 4. Обрабатываем сообщение в транзакции
            async with env.apps.db.get_transaction():
                await self._process_incoming_message(env, connector, adapter)

            return {"ok": True}

        except NotImplementedError as e:
            logger.warning("[%s] Not implemented: %s", self.strategy_type, e)
            return {"ok": True}
        except Exception as e:
            logger.error(
                "[%s] Error processing webhook: %s",
                self.strategy_type,
                e,
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
        6. Создать/обновить лид по правилам (lead generation)
        7. Отправить через WebSocket
        """

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
            # Перечитываем external_chat после создания, чтобы получить
            # обновлённые поля item_title/item_url для лидогенерации.
            external_chat = (
                await env.models.chat_external_chat.find_by_external_id(
                    external_id=adapter.chat_id,
                    connector_id=connector.id,
                )
            )

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

        # 7. Лидогенерация — только для сообщений от клиента (не операторов)
        if connector.lead_generation:
            try:
                if author_partner_id:
                    await self._get_or_create_lead(
                        env=env,
                        connector=connector,
                        adapter=adapter,
                        contact=contact,
                        external_chat=external_chat,
                    )
            except Exception as exc:  # noqa: BLE001
                # Лидогенерация не должна валить обработку сообщения целиком.
                logger.warning(
                    "[%s] Lead generation failed for message %s: %s",
                    self.strategy_type,
                    adapter.message_id,
                    exc,
                    exc_info=True,
                )

        # 8. Отправляем уведомление через WebSocket
        author_data = {
            "id": author_user_id or author_partner_id,
            "name": adapter.author_name,
            "type": "user" if author_user_id else "partner",
        }

        await env.apps.chat.chat_manager.send_to_chat(
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
                    "create_datetime": (
                        message.create_datetime.isoformat()
                        if message.create_datetime
                        else None
                    ),
                    "connector_type": connector.type,
                },
                "external": True,
            },
        )

        logger.info(
            "[%s] Processed message %s -> internal %s",
            self.strategy_type,
            adapter.message_id,
            message.id,
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
                "[%s] No operator available for connector %s",
                self.strategy_type,
                connector.id,
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
            create_datetime=now,
            update_datetime=now,
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

        # Сразу получаем item_title/item_url у стратегии, чтобы записать
        # их в cache на chat_external_chat (использует и лидогенерация,
        # и UI). Безопасно: если стратегия не умеет — вернёт пустые.
        item_title, item_url = await self._fetch_item_info(connector, adapter)

        # Создаём связь с внешним чатом и сам внешний чат
        await env.models.chat_external_chat.create_link(
            external_id=adapter.chat_id,
            connector_id=connector.id,
            chat_id=chat_id,
            item_title=item_title,
            item_url=item_url,
        )

        logger.info(
            "[%s] Created new chat %s for external %s",
            self.strategy_type,
            chat_id,
            adapter.chat_id,
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
                    "[%s] Downloaded image: %s bytes",
                    self.strategy_type,
                    len(image_content),
                )
            except Exception as e:
                logger.error(
                    "[%s] Error downloading image: %s", self.strategy_type, e
                )

        for file_info in adapter.files:
            try:
                file_content = await self.file_download(
                    connector, file_info.get("url", "")
                )
                # TODO: Интеграция с модулем attachments
                logger.debug(
                    "[%s] Downloaded file: %s (%s bytes)",
                    self.strategy_type,
                    file_info.get("name"),
                    len(file_content),
                )
            except Exception as e:
                logger.error(
                    "[%s] Error downloading file: %s", self.strategy_type, e
                )

    # Лидогенерация
    async def _fetch_item_info(
        self,
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> tuple[str, str]:
        """Получить (item_title, item_url) у стратегии.

        Не все коннекторы поддерживают объявления/контекст; такие
        вернут пустые строки. Avito-стратегия переопределяет
        `get_item_info` и возвращает реальные данные.
        """
        item_title = ""
        item_url = ""
        try:
            user_id = getattr(adapter, "user_id", None)
            item_id = getattr(adapter, "item_id", None)
            chat_id = getattr(adapter, "chat_id", None)
            # user_id может быть методом — это известно для Avito-адаптера
            # if callable(user_id):
            #     user_id = user_id()
            get_item_info = getattr(self, "get_item_info", None)
            if get_item_info is not None and chat_id:
                info = (
                    await get_item_info(
                        connector, user_id, item_id, chat_id=chat_id
                    )
                    or {}
                )
                item_title = info.get("title") or ""
                item_url = info.get("url") or ""
            else:
                # Fallback на отдельный get_item_url, если стратегия даёт только его.
                if item_id:
                    item_url = (
                        await self.get_item_url(connector, user_id, item_id)
                        or ""
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] Cannot fetch item info: %s",
                self.strategy_type,
                exc,
            )
        return item_title, item_url

    def _build_routing_payload(
        self,
        adapter: "ChatMessageAdapter",
        contact: "Contact",
        item_title: str,
        item_url: str,
        partner_name: str = "",
    ) -> dict:
        """Сформировать словарь для проверки правил маршрутизации.

        Структура (item_title, message_text, item_url,
        partner_name) — это позволяет администратору применять одни и
        те же правила между системами.
        """
        if not partner_name and contact and contact.partner_id:
            # Может быть stub — name не загружен; не страшно, fallback ниже.
            partner_name = getattr(contact.partner_id, "name", None) or ""
        if not partner_name:
            partner_name = getattr(adapter, "author_name", None) or ""
        return {
            "item_title": item_title or "",
            "message_text": adapter.text or "",
            "item_url": item_url or "",
            "partner_name": partner_name,
        }

    async def _get_or_create_lead(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
        contact: "Contact",
        external_chat,
    ):
        """Создать или найти существующий лид для входящего сообщения.

        Логика:
        - имя лида = item_title (заголовок объявления) или partner.name;
        - ищем существующий лид по (parent_id, connector_id);
        - если у найденного лида другой website (item_url) — создаём новый
          (клиент пишет по другому объявлению — это другой лид);
        - применяем правила chat_routing_rule_lead если включено
          `connector.lead_distribution`.
        """
        partner = contact.partner_id if contact else None
        if not partner:
            # Без партнёра-клиента создавать лид бессмысленно.
            return None

        # partner здесь может быть "stub" (только id, без полей) — дочерние
        # поля типа .name не подгружаются автоматически. Поэтому если name
        # пустое — догружаем явно из БД (один лёгкий запрос).
        partner_name = partner.name
        # partner_name = getattr(partner, "name", None)
        # if not partner_name:
        #     loaded_partners = await env.models.partner.search(
        #         filter=[("id", "=", partner.id)],
        #         fields=["id", "name"],
        #         limit=1,
        #     )
        #     if loaded_partners:
        #         partner_name = loaded_partners[0].name or ""
        #     else:
        #         partner_name = ""

        # item_title / item_url — из кеша chat_external_chat
        item_title = ""
        item_url = ""
        if external_chat:
            item_title = (external_chat.item_title or "").strip()
            item_url = (external_chat.item_url or "").strip()

        # Ищем существующий лид по (parent_id, connector_id) — берём свежий
        existing_leads = await env.models.lead.search(
            filter=[
                ("parent_id", "=", partner.id),
                ("connector_id", "=", connector.id),
            ],
            fields=["id", "website", "name"],
            sort="id",
            order="DESC",
            limit=1,
        )
        existing_lead = existing_leads[0] if existing_leads else None

        # Если у найденного лида другой website — этот клиент пишет по
        # другому объявлению, создаём новый лид.
        if (
            existing_lead
            and item_url
            and existing_lead.website
            and existing_lead.website != item_url
        ):
            existing_lead = None

        if existing_lead:
            # Обновим website если он появился позже
            if item_url and existing_lead.website != item_url:
                await existing_lead.update(env.models.lead(website=item_url))
            return existing_lead

        # Имя лида: заголовок объявления или имя партнёра.
        fallback_name = (
            partner_name
            or getattr(adapter, "author_name", None)
            or f"Lead {connector.name or connector.type}"
        )
        lead_name = item_title or fallback_name

        # Правила маршрутизации
        assigned_user = None
        assigned_team = None
        if connector.lead_distribution:
            try:
                rule_user, rule = (
                    await env.models.chat_routing_rule_lead.find_user_for(
                        connector.id,
                        self._build_routing_payload(
                            adapter,
                            contact,
                            item_title,
                            item_url,
                            partner_name=partner_name,
                        ),
                    )
                )
                if rule_user:
                    assigned_user = rule_user
                    if rule and rule.team_id:
                        assigned_team = rule.team_id
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[%s] Routing rule evaluation failed: %s",
                    self.strategy_type,
                    exc,
                )

        # Собираем payload для нового лида
        lead_payload = {
            "name": lead_name,
            "type": connector.lead_type or "opportunity",
            "parent_id": partner,
            "connector_id": env.models.chat_connector(id=connector.id),
            "website": item_url or None,
            "notes": (
                f"Создан из сообщения {adapter.message_id} ({connector.name})"
            ),
        }
        if assigned_user:
            lead_payload["user_id"] = assigned_user
        if assigned_team:
            lead_payload["team_id"] = assigned_team
        if connector.lead_stage_id:
            lead_payload["stage_id"] = connector.lead_stage_id

        new_lead = env.models.lead(**lead_payload)
        new_lead.id = await env.models.lead.create(payload=new_lead)
        logger.info(
            "[%s] Created lead %s (name=%r) for partner %s via connector %s",
            self.strategy_type,
            new_lead.id,
            lead_name,
            partner.id,
            connector.id,
        )
        return new_lead

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

    async def get_self_account_id(self, connector: "ChatConnector") -> dict:
        """
        Получить информацию об аккаунте от внешнего сервиса.

        Конкретные стратегии (Avito) переопределяют — возвращают данные
        текущего аккаунта (id, name, email, phone, profile_url и т.п.),
        чтобы пользователь мог скопировать `external_account_id` при
        настройке коннектора.

        Returns:
            Словарь с данными аккаунта от провайдера.
        """
        raise NotImplementedError(
            f"get_self_account_id not supported for {self.strategy_type}"
        )

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
                        "Multiple recipients not fully supported yet, using first one"
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
                    "No external_chat found for chat=%s, connector=%s and no recipients provided",
                    chat_id,
                    connector_id.id,
                )
                return False

            # Находим контакт оператора по contact_type_id коннектора
            operator_ct_id = connector_id.contact_type_id
            if operator_ct_id is None:
                raise ValueError("Contact type must be set")

            operator_contact = await env.models.contact.search(
                filter=[
                    ("contact_type_id", "=", operator_ct_id.id),
                    ("user_id", "=", user_id),
                    ("active", "=", True),
                ],
                limit=1,
            )

            if not operator_contact:
                logger.warning(
                    "No operator contact found for connector %s, user %s",
                    connector_id.id,
                    user_id,
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
                            "Failed to send attachment %s: %s",
                            att.get("id"),
                            e,
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
                "Sent message to %s: internal=%s, external=%s",
                connector_id.type,
                message_id,
                external_msg_id,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to send to external connector: %s", e, exc_info=True
            )
            return False
