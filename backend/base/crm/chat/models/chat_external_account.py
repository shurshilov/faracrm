# Copyright 2025 FARA CRM
# Chat module - external account model

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Selection,
    Text,
    Boolean,
    Datetime,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.partners.models.contact import Contact
    from backend.base.crm.chat.models.chat_connector import ChatConnector

logger = logging.getLogger(__name__)


class ChatExternalAccount(DotModel):
    """
    Внешний аккаунт в мессенджере.

    Связывает Contact с аккаунтом во внешнем сервисе (Telegram, WhatsApp и т.д.).

    Структура:
    - Contact хранит контактные данные (телефон, email, username) в поле name
    - ChatExternalAccount хранит техническую связь с мессенджером (external_id)

    Пример:
    - Contact(type=phone, name=+79991234567)
      └── ChatExternalAccount(connector=WhatsApp, external_id=WA_123)
      └── ChatExternalAccount(connector=Viber, external_id=VB_456)

    - Contact(type=telegram, name=@ivanov)
      └── ChatExternalAccount(connector=TelegramBot, external_id=123456789)
    """

    __table__ = "chat_external_account"

    id: int = Integer(primary_key=True)

    # Основная информация
    name: str | None = Char(max_length=255, description="Имя аккаунта")
    active: bool = Boolean(default=True)

    # Внешний идентификатор в стороннем сервисе
    external_id: str = Char(
        max_length=255,
        required=True,
        description="ID в внешней системе (telegram user_id, whatsapp id...)",
    )

    # Связь с коннектором
    connector_id: "ChatConnector" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        required=True,
        ondelete="cascade",
        description="Коннектор",
    )

    # Связь с контактом (НОВОЕ - заменяет partner_id/user_id)
    contact_id: "Contact | None" = Many2one(
        relation_table=lambda: env.models.contact,
        ondelete="cascade",
        description="Контакт (владелец через contact.partner_id или contact.user_id)",
        index=True,
    )

    # Дополнительные данные
    raw: str | None = Text(
        description="Сырые данные из которых создан аккаунт"
    )

    # Порядок для распределения (для операторов)
    sequence: int = Integer(default=10, description="Порядок в очереди")

    # Статистика (вычисляемые поля)
    # rating: int = Integer(store=False, default=0, description="Количество чатов")
    # rating_today: int = Integer(store=False, default=0, description="Количество чатов сегодня")

    # Временные метки
    create_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )
    write_date: datetime = Datetime(default=lambda: datetime.now(timezone.utc))

    # Лидогенерация
    # при отвеченном звонке
    lead_generation: str | None = Selection(
        options=[
            ("self", "Create lead (assigned to operator)"),
            ("common", "Create common lead (unassigned)"),
            ("no", "Do not create lead"),
        ],
        default="no",
        description=(
            "Правило создания лида при отвеченном звонке на этот номер. "
            "self = лид с ответственным оператором, "
            "common = лид без ответственного, "
            "no = не создавать"
        ),
    )

    # при пропущенном звонке
    lead_generation_missed: str | None = Selection(
        options=[
            ("self", "Create lead (assigned to operator)"),
            ("common", "Create common lead (unassigned)"),
            ("no", "Do not create lead"),
        ],
        default="no",
        description=(
            "Правило создания лида при пропущенном звонке. "
            "Аналогично lead_generation, но для пропущенных"
        ),
    )

    @property
    def is_operator(self) -> bool:
        """Является ли аккаунт оператором (сотрудником)."""
        return (
            self.contact_id is not None and self.contact_id.user_id is not None
        )

    @property
    def partner_id(self):
        """Получить партнёра через контакт (для совместимости)."""
        if self.contact_id:
            return self.contact_id.partner_id
        return None

    @property
    def user_id(self):
        """Получить пользователя через контакт (для совместимости)."""
        if self.contact_id:
            return self.contact_id.user_id
        return None

    async def find_by_external_id(
        self, external_id: str, connector_id: int
    ) -> "ChatExternalAccount | None":
        """
        Найти аккаунт по внешнему ID и коннектору.
        """
        accounts = await self.search(
            filter=[
                ("external_id", "=", external_id),
                ("connector_id", "=", connector_id),
                ("active", "=", True),
            ],
            fields=["id", "contact_id", "external_id", "name"],
            # fields_nested={"contact_id": ["user_id", "partner_id"]},
            limit=1,
        )
        return accounts[0] if accounts else None

    @hybridmethod
    async def find_or_create_for_webhook(
        self,
        connector: "ChatConnector",
        external_id: str,
        contact_value: str | None = None,
        display_name: str | None = None,
        raw: str | None = None,
    ) -> tuple["ChatExternalAccount", "Contact", bool]:
        """
        Найти или создать ExternalAccount для входящего webhook.

        Потоки:
            A) Аккаунт уже существовал и привязан к контакту — отдаём его.
            B) Аккаунта нет (или он без контакта) — резолвим контакт через
               Contact.find_for_webhook (exact → phone-format fallback); если
               не нашли — Contact.create_with_partner создаёт Partner+Contact.
               Затем создаём или доcвязываем аккаунт.

        Args:
            connector: Коннектор.
            external_id: ID из API мессенджера.
            contact_value: Человекочитаемое значение (@username, +7999...) —
                           сохраняется в Contact.name.
            display_name: Имя из профиля (для нового Partner и ExternalAccount.name).
            raw: Сырые данные webhook.

        Returns:
            (account, contact, created) — created=True, если в рамках вызова
            был создан новый Contact (не просто новый аккаунт).
        """
        # Поток A — аккаунт уже привязан к контакту
        existing = await self.find_by_external_id(external_id, connector.id)
        if existing and existing.contact_id:
            contacts = await env.models.contact.search(
                filter=[("id", "=", existing.contact_id.id)],
                fields=["id", "name", "user_id", "partner_id"],
                limit=1,
            )
            return existing, contacts[0], False

        # Поток B — резолв/создание контакта + создание/доcвязка аккаунта
        if connector.contact_type_id is None:
            raise ValueError("Contact type must be set")
        contact_type = connector.contact_type_id

        contact = await env.models.contact.find_for_webhook(
            contact_type=contact_type,
            value=contact_value,
        )
        created = contact is None
        if created:
            contact = await env.models.contact.create_with_partner(
                contact_type=contact_type,
                value=contact_value or external_id,
                partner_name=display_name or f"Client {external_id}",
            )
            logger.info(
                "Created Partner %s with Contact %s for external_id=%s",
                contact.partner_id.id if contact.partner_id else None,
                contact.id,
                external_id,
            )

        account = await self._attach_account(
            existing=existing,
            connector=connector,
            contact=contact,
            external_id=external_id,
            contact_value=contact_value,
            display_name=display_name,
            raw=raw,
        )
        return account, contact, created

    @hybridmethod
    async def _attach_account(
        self,
        existing: "ChatExternalAccount | None",
        connector: "ChatConnector",
        contact: "Contact",
        external_id: str,
        contact_value: str | None,
        display_name: str | None,
        raw: str | None,
    ) -> "ChatExternalAccount":
        """
        Привязать аккаунт к контакту.

        Если пришёл existing (аккаунт был, но без contact_id) — доcвязываем.
        Иначе создаём новый ChatExternalAccount.
        """
        if existing:
            await existing.update(ChatExternalAccount(contact_id=contact))
            return existing

        account = ChatExternalAccount(
            name=display_name or contact_value or external_id,
            external_id=external_id,
            connector_id=connector,
            contact_id=contact,
            raw=raw,
        )
        account.id = await self.create(payload=account)
        logger.info(
            "Created ChatExternalAccount %s linked to Contact %s",
            account.id,
            contact.id,
        )
        return account
