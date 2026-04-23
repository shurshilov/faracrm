# Copyright 2025 FARA CRM
# Chat module - connector model for external integrations

import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Self

from backend.base.system.dotorm.dotorm.components.filter_parser import (
    FilterExpression,
)
from backend.base.system.dotorm.dotorm.decorators import hybridmethod, onchange
from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Text,
    Boolean,
    Datetime,
    Selection,
    Many2one,
    One2many,
    Many2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.chat.strategies import get_strategy

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.contact_type import ContactType

logger = logging.getLogger(__name__)


class ChatConnector(DotModel):
    """
    Модель коннектора для интеграции с внешними сервисами.

    Поддерживаемые типы (расширяются через стратегии):
    - internal: внутренний чат FARA CRM
    - telegram: Telegram Bot API
    - whatsapp: WhatsApp Business API
    - и другие...

    Архитектура основана на паттерне Strategy для легкого добавления
    новых провайдеров без изменения основного кода.
    """

    __table__ = "chat_connector"

    id: int = Integer(primary_key=True)

    # Основная информация
    name: str = Char(max_length=255, description="Название коннектора")
    active: bool = Boolean(default=True, description="Активен")

    # Тип коннектора - определяет какую стратегию использовать
    # Расширяется через @extend с selection_add из модулей провайдеров
    type: str = Selection(
        options=[
            ("internal", "Internal"),
        ],
        default="internal",
        required=True,
        description="Тип коннектора (определяет API для работы)",
    )

    # Категория для группировки и поиска
    category: str = Selection(
        options=[
            ("messenger", "Messenger"),
            ("notification", "Notification"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("social", "Social"),
        ],
        default="messenger",
        required=True,
        description="Категория: messenger, phone, email, social",
    )

    # Тип контакта, с которым работает коннектор
    # WhatsApp → phone, Telegram → telegram, Email → email, и т.д.
    contact_type_id: "ContactType | None" = Many2one(
        relation_table=lambda: env.models.contact_type,
        ondelete="set null",
        description="Тип контакта, с которым работает коннектор",
        index=True,
    )

    # URL для API коннектора
    connector_url: str | None = Char(
        max_length=500,
        description="URL API коннектора (например, https://api.telegram.org)",
    )

    # Webhook настройки
    webhook_url: str | None = Char(
        max_length=500, description="URL вебхука для приёма сообщений"
    )
    webhook_hash: str | None = Char(
        max_length=128, description="Секретный хеш для валидации вебхуков"
    )
    webhook_state: str = Selection(
        options=[
            ("none", "None"),
            ("successful", "Successful"),
            ("failed", "Failed"),
        ],
        default="none",
        description="Статус вебхука",
    )

    # Токены авторизации
    access_token: str | None = Text(description="Access Token для API")
    access_token_expired: datetime | None = Datetime(
        description="Срок действия access token"
    )
    refresh_token: str | None = Text(description="Refresh Token")
    refresh_token_expired: datetime | None = Datetime(
        description="Срок действия refresh token"
    )
    access_token_type: str | None = Char(
        max_length=50, description="Тип токена (Bearer и т.д.)"
    )

    # Идентификаторы приложения
    client_app_id: str | None = Char(
        max_length=255, description="ID клиентского приложения"
    )
    # Идентификатор внешнего аккаунта от чьего имени работаем
    external_account_id: str | None = Char(
        max_length=255, description="ID внешнего аккаунта"
    )

    # Флаг: дублировать ли уведомления через этот коннектор
    # Если True — при новом сообщении в любом чате,
    # пользователям-участникам отправляется уведомление через этот коннектор
    notify: bool = Boolean(
        default=False,
        description="Отправлять уведомления о новых сообщениях через этот коннектор",
    )

    # Настройки создания лидов
    lead_type: str = Selection(
        options=[
            ("lead", "Lead"),
            ("opportunity", "Opportunity"),
        ],
        default="opportunity",
        description="Тип создаваемых лидов",
    )

    # Логирование
    last_response: str | None = Text(description="Последний ответ от API")

    # Временные метки
    create_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )
    write_date: datetime = Datetime(default=lambda: datetime.now(timezone.utc))

    # Связанные внешние аккаунты (операторы и клиенты)
    # в основном просто для информации, нигде не используется
    account_ids: list["ChatExternalAccount"] = One2many(
        store=False,
        relation_table=lambda: env.models.chat_external_account,
        relation_table_field="connector_id",
        description="Аккаунты в этом коннекторе",
    )

    # Операторы коннектора (Many2many с User)
    operator_ids: list["User"] = Many2many(
        store=False,
        relation_table=lambda: env.models.user,
        many2many_table="chat_connector_operator_many2many",
        column1="user_id",
        column2="connector_id",
        ondelete="cascade",
        description="Операторы, работающие с этим коннектором",
        default=[],
    )

    @onchange("type")
    async def onchange_type(self) -> dict:
        first_type = await env.models.contact_type.search(
            filter=[("name", "=", self.type)],
            fields=["id", "name"],
            limit=1,
        )
        if first_type:
            return {"contact_type_id": first_type[0]}
        else:
            return {"contact_type_id": None}

    @hybridmethod
    async def create(self, payload: Self, session=None) -> int:
        """
        Создание коннектора с автоматическим созданием ChatExternalAccount
        для назначенных операторов.
        """
        # Создаём коннектор (Many2many operator_ids заполнится автоматически)
        self.id = await super().create(payload=payload, session=session)

        # Получаем операторов из Many2many таблицы
        new_operator_ids = await self._get_current_operator_ids()

        # Создаём ChatExternalAccount для операторов
        if new_operator_ids:
            await self._sync_operators(self.id, [], new_operator_ids)

        return self.id

    @hybridmethod
    async def update(self, payload, fields=None, session=None):
        """
        Обновление коннектора с синхронизацией Contact для операторов.
        """
        # Проверяем, изменяются ли операторы
        has_operator_changes = fields and "operator_ids" in fields

        old_operator_ids = []
        if has_operator_changes:
            old_operator_ids = await self._get_current_operator_ids()

        # Выполняем обновление (включая Many2many)
        result = await super().update(payload, fields, session=session)

        # Синхронизируем Contact если были изменения операторов
        if has_operator_changes:
            new_operator_ids = await self._get_current_operator_ids()
            if old_operator_ids != new_operator_ids:
                await self._sync_operators(
                    self.id, old_operator_ids, new_operator_ids
                )

        return result

    async def _get_current_operator_ids(self) -> list[int]:
        """Получить текущий список ID операторов из БД."""
        query = """
            SELECT user_id FROM chat_connector_operator_many2many
            WHERE connector_id = $1
        """
        session = env.apps.db.get_session()
        result = await session.execute(query, [self.id], cursor="fetch")
        return [row["user_id"] for row in result]

    async def _sync_operators(
        self, connector_id: int, old_ids: list[int], new_ids: list[int]
    ) -> None:
        """
        Синхронизировать Contact при изменении списка операторов.

        - Для добавленных операторов: создать Contact
        - Для удалённых операторов: деактивировать Contact
        """
        old_set = set(old_ids)
        new_set = set(new_ids)

        added = list(new_set - old_set)
        removed = list(old_set - new_set)

        if not added and not removed:
            return

        connector = await self.search(
            filter=[("id", "=", connector_id)],
            # fields=["id", "name", "external_account_id", "contact_type_id"],
        )
        if not connector:
            raise ValueError(f"Connector {connector_id} not found")
        connector = connector[0]

        if not connector.contact_type_id:
            raise ValueError(
                f"Contact type not set for connector {connector_id}"
            )

        contact_type = connector.contact_type_id
        contact_value = connector.external_account_id or connector.name

        if added:
            # Загружаем пользователей и существующие контакты параллельно (если позволяет движок)
            users = await env.models.user.search(
                filter=[("id", "in", added)], fields=["id", "name"]
            )
            users_map = {u.id: u for u in users}

            existing_contacts = await env.models.contact.search(
                filter=[
                    ("user_id", "in", added),
                    ("contact_type_id", "=", contact_type.id),
                ],
                fields=["id", "name", "user_id"],
            )
            existing_contacts_map = {
                c.user_id.id: c for c in existing_contacts if c.user_id
            }

            # 1. Реактивация (исправлено active=True)
            to_reactivate = [c.id for c in existing_contacts if not c.active]
            if to_reactivate:
                await env.models.contact.update_bulk(
                    to_reactivate, env.models.contact(active=True)
                )
                logger.info("Reactivated %s contacts", len(to_reactivate))

            # 2. Создание новых
            new_contacts = [
                env.models.contact(
                    user_id=users_map[uid],
                    contact_type_id=contact_type,
                    name=contact_value,
                    is_primary=True,
                    active=True,
                )
                for uid in added
                if uid in users_map and uid not in existing_contacts_map
            ]

            if new_contacts:
                await env.models.contact.create_bulk(new_contacts)
                logger.info("Created %s new contacts", len(new_contacts))

        if removed:
            # Сразу ищем активные контакты для удаления
            to_deactivate = await env.models.contact.search(
                filter=[
                    ("user_id", "in", removed),
                    ("contact_type_id", "=", contact_type.id),
                    ("active", "=", True),
                ],
                fields=["id"],
            )
            if to_deactivate:
                ids = [c.id for c in to_deactivate]
                await env.models.contact.update_bulk(
                    ids, env.models.contact(active=False)
                )
                logger.info("Deactivated %s contacts", len(ids))

    async def get_next_operator(self):
        """
        Получить следующего доступного оператора для распределения чата.

        Returns:
            Пользователь-оператор или None
        """
        operators = await self._get_current_operator_ids()

        if not operators:
            return None

        # TODO: Реализовать round-robin или load balancing
        # Пока возвращаем первого
        return operators[0]

    @property
    def strategy(self):
        """
        Получить стратегию для данного типа коннектора.
        Стратегии регистрируются в env.chat_strategies
        """

        return get_strategy(self.type)

    async def set_webhook(self, api_url: str | None = None) -> bool:
        """
        Установить вебхук.

        Args:
            api_url: URL бэкенда снаружи. Если не указан, берётся из
                     SystemSettings (core.api_url).
                     Это именно api_url, а не site_url: webhook
                     приземляется на роут бэкенда (/chat/webhook/...),
                     а не на фронт.
        """
        try:
            # Генерируем webhook_url если его нет
            if not self.webhook_url:
                if not api_url:
                    settings_api_url = (
                        await env.models.system_settings.get_api_url()
                    )
                    api_url = (
                        settings_api_url
                        if isinstance(settings_api_url, str)
                        else "http://127.0.0.1:8090"
                    )

                self.webhook_url = self.generate_webhook_url(api_url)

            await self.strategy.set_webhook(self)
            await self.update(
                ChatConnector(
                    webhook_url=self.webhook_url,
                    webhook_state="successful",
                )
            )
            return True
        except Exception as e:
            await self.update(
                ChatConnector(
                    webhook_state="failed",
                    last_response=str(e),
                )
            )
            return False

    async def unset_webhook(self) -> bool:
        """Удалить вебхук."""
        try:
            response = await self.strategy.unset_webhook(self)
            await self.update(
                ChatConnector(
                    webhook_state="none",
                    last_response=str(response),
                )
            )
            return True
        except Exception as e:
            await self.update(
                ChatConnector(last_response=str(e), webhook_state="failed"),
            )
            return False

    async def get_active_connectors(
        self,
        connector_type: str | None = None,
        category: str | None = None,
    ):
        """Получить активные коннекторы с опциональной фильтрацией."""
        filter_conditions: FilterExpression = [("active", "=", True)]

        if connector_type:
            filter_conditions.append(("type", "=", connector_type))

        if category:
            filter_conditions.append(("category", "=", category))

        return await self.search(
            filter=filter_conditions,
            fields=[
                "id",
                "name",
                "type",
                "category",
                "connector_url",
                "webhook_state",
            ],
        )

    async def cron_refresh_tokens(self):
        """
        Cron задача для обновления токенов всех активных коннекторов.
        """
        connectors = await self.get_active_connectors()

        # Создаем список задач
        tasks = [
            connector.strategy.get_or_generate_token(self)
            for connector in connectors
        ]

        # Запускаем всё параллельно.
        # return_exceptions=True позволит собрать результаты, даже если один упал.
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Логируем ошибки, если они были
        for connector, result in zip(connectors, results):
            if isinstance(result, Exception):
                logger.error(
                    f"Failed to refresh token for {connector.id}: {result}"
                )

    def generate_webhook_url(self, api_url: str) -> str:
        """
        Генерирует webhook URL для коннектора.

        Args:
            api_url: URL бэкенда снаружи (см. set_webhook).

        Returns:
            Полный webhook URL
        """
        if not self.id:
            raise ValueError("ID is required to generate webhook URL")

        # Убеждаемся, что хеш есть, но лучше это делать при создании записи
        if not self.webhook_hash:
            self.webhook_hash = secrets.token_hex(32)

        # Убираем лишние слеши, если api_url пришел с '/' в конце
        clean_url = api_url.rstrip("/")
        return f"{clean_url}/chat/webhook/{self.webhook_hash}/{self.id}"
