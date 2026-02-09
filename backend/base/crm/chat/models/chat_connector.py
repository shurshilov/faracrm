# Copyright 2025 FARA CRM
# Chat module - connector model for external integrations

import logging
import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Self

from backend.base.system.dotorm.dotorm.components.filter_parser import (
    FilterExpression,
)
from backend.base.system.dotorm.dotorm.decorators import hybridmethod
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

    @hybridmethod
    async def create(self, payload: Self, session=None) -> int:
        """
        Создание коннектора с автоматическим созданием ChatExternalAccount
        для назначенных операторов.
        """
        # Создаём коннектор (Many2many operator_ids заполнится автоматически)
        connector_id = await super().create(payload=payload, session=session)

        # Получаем операторов из Many2many таблицы
        self.id = connector_id
        new_operator_ids = await self._get_current_operator_ids()

        # Создаём ChatExternalAccount для операторов
        if new_operator_ids:
            await self._sync_operators(connector_id, [], new_operator_ids)

        return connector_id

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

        added = new_set - old_set
        removed = old_set - new_set

        if not added and not removed:
            return

        # Получаем данные коннектора
        connector = await self.get(
            connector_id,
            fields=[
                "id",
                "name",
                "type",
                "external_account_id",
                "contact_type_id",
            ],
        )

        # Определяем тип контакта для этого коннектора (Many2one → contact_type)
        contact_type_id = connector.contact_type_id
        if contact_type_id is None:
            raise ValueError("Contact type must be set")

        # Значение контакта — ID аккаунта из коннектора
        contact_value = connector.external_account_id or connector.name

        # Batch: получаем всех пользователей за один запрос
        users_map = {}
        if added:
            users = await env.models.user.search(
                filter=[("id", "in", list(added))],
                fields=["id", "name"],
            )
            users_map = {u.id: u for u in users}

        # Batch: получаем существующие контакты для добавляемых операторов
        existing_contacts_map = {}
        if added:
            existing_contacts = await env.models.contact.search(
                filter=[
                    ("user_id", "in", list(added)),
                    ("contact_type_id", "=", contact_type_id.id),
                ],
            )
            existing_contacts_map = {
                c.user_id.id: c for c in existing_contacts if c.user_id
            }

        # Создаём/реактивируем Contact для добавленных операторов
        # Реактивируем неактивные контакты
        contacts_to_reactivate = [
            c
            for c in existing_contacts_map.values()
            if c.user_id and c.user_id.id in added and not c.active
        ]
        if contacts_to_reactivate:
            ids = [c.id for c in contacts_to_reactivate]
            await env.models.contact.update_bulk(
                ids, env.models.contact(active=False)
            )
            logger.info(f"Reactivated {len(ids)} contacts for operators")

        # Создаём новые контакты для операторов без существующих
        new_contacts = []
        for user_id in added:
            user = users_map.get(user_id)
            if not user:
                continue

            if user_id not in existing_contacts_map:
                new_contacts.append(
                    env.models.contact(
                        user_id=user,
                        contact_type_id=contact_type_id,
                        name=contact_value,
                        is_primary=True,
                    )
                )

        if new_contacts:
            await env.models.contact.create_bulk(new_contacts)
            logger.info(f"Created {len(new_contacts)} contacts for operators")

        # Batch: деактивируем Contact для удалённых операторов
        if removed:
            contacts_to_deactivate = await env.models.contact.search(
                filter=[
                    ("user_id", "in", list(removed)),
                    ("contact_type_id", "=", contact_type_id.id),
                    ("active", "=", True),
                ],
            )
            if contacts_to_deactivate:
                ids = [c.id for c in contacts_to_deactivate]
                await env.models.contact.update_bulk(
                    ids, env.models.contact(active=False)
                )
                logger.info(
                    f"Deactivated {len(ids)} contacts for removed operators"
                )

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
        from backend.base.crm.chat.strategies import get_strategy

        return get_strategy(self.type)

    async def get_or_generate_token(self) -> str | None:
        """
        Получить существующий токен или сгенерировать новый.
        Делегирует логику стратегии.
        """
        return await self.strategy.get_or_generate_token(self)

    async def set_webhook(self, base_url: str | None = None) -> bool:
        """
        Установить вебхук.

        Args:
            base_url: Базовый URL сервера. Если не указан, берётся из SystemSettings.
        """
        try:
            # Генерируем webhook_url если его нет
            if not self.webhook_url:
                if not base_url:
                    base_url = await env.models.system_settings.get_base_url()
                    if not base_url:
                        base_url = "http://127.0.0.1"

                self.webhook_url = self.generate_webhook_url(base_url)

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
            await self.update(ChatConnector(last_response=str(e)))
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

        for connector in connectors:
            try:
                await connector.get_or_generate_token()
            except Exception:
                # Логируем ошибку но продолжаем для других коннекторов
                pass

    def generate_webhook_url(self, base_url: str) -> str:
        """
        Генерирует webhook URL для коннектора.

        Args:
            base_url: Базовый URL сервера

        Returns:
            Полный webhook URL
        """
        if not self.id:
            raise ValueError("Cannot generate webhook_url without ID")
        if not self.webhook_hash:
            self.webhook_hash = secrets.token_hex(32)

        return f"{base_url}/chat/webhook/{self.webhook_hash}/{self.id}"
