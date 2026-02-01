# Copyright 2025 FARA CRM
# Chat module - external account model

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
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

    # ==================== Properties ====================

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

    # ==================== Instance Methods ====================

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
        Найти или создать аккаунт для входящего webhook.

        Алгоритм:
        1. Ищем ExternalAccount по (connector_id, external_id)
        2. Если нашли — возвращаем вместе с контактом
        3. Если нет — ищем Contact по contact_value
        4. Если нет Contact — создаём Partner + Contact
        5. Создаём ExternalAccount привязанный к Contact

        Args:
            connector: Коннектор
            external_id: ID из API мессенджера
            contact_value: Человекочитаемое значение (@username, +7999...) — сохраняется в Contact.name
            display_name: Имя из профиля (для создания партнёра и ExternalAccount.name)
            raw: Сырые данные webhook

        Returns:
            Tuple[ChatExternalAccount, Contact, created: bool]
        """
        # 1. Ищем существующий ExternalAccount
        existing = await self.find_by_external_id(external_id, connector.id)
        if existing and existing.contact_id:
            contact = await env.models.contact.search(
                filter=[("id", "=", existing.contact_id.id)],
                fields=["id", "partner_id", "user_id", "name"],
            )
            return existing, contact[0], False

        # 2. Определяем тип контакта для этого коннектора (через contact_type_id на коннекторе)
        contact_type_id = None
        if connector.contact_type_id:
            contact_type_id = connector.contact_type_id.id

        if not contact_type_id:
            contact_type_id = await env.models.contact_type.get_contact_type_id_for_connector(
                connector.type
            )

        # 3. Ищем Contact по name (значению контакта)
        contact = None
        if contact_value and contact_type_id:
            contacts = await env.models.contact.search(
                filter=[
                    ("contact_type_id", "=", contact_type_id),
                    ("name", "=", contact_value),
                    ("active", "=", True),
                ],
                fields=["id", "name", "user_id", "partner_id"],
                limit=1,
            )
            if contacts:
                contact = contacts[0]

        # 4. Если Contact не найден — ищем по родительскому типу
        # (например whatsapp-коннектор → ищем контакт типа phone)
        if not contact and contact_value and contact_type_id:
            # Получаем name текущего contact_type
            ct_name = (
                await env.models.contact_type.get_contact_type_for_connector(
                    connector.type
                )
            )
            if ct_name:
                # Ищем контакт по name типа (phone для whatsapp)
                ct_obj = await env.models.contact_type.get_by_name(ct_name)
                if ct_obj and ct_obj.id != contact_type_id:
                    fallback_contacts = await env.models.contact.search(
                        filter=[
                            ("contact_type_id", "=", ct_obj.id),
                            ("name", "=", contact_value),
                            ("active", "=", True),
                        ],
                        fields=["id", "name", "user_id", "partner_id"],
                        limit=1,
                    )
                    if fallback_contacts:
                        contact = fallback_contacts[0]

        # 5. Если Contact не найден — создаём Partner + Contact
        created = False
        if not contact:
            partner_name = display_name or f"Client {external_id}"
            partner = env.models.partner(name=partner_name)
            partner.id = await env.models.partner.create(payload=partner)

            contact = env.models.contact(
                user_id=None,
                partner_id=partner,
                contact_type_id=contact_type_id,
                name=contact_value or external_id,
                is_primary=True,
            )
            contact.id = await env.models.contact.create(payload=contact)
            created = True

            logger.info(
                f"Created Partner {partner.id} with Contact {contact.id} "
                f"for external_id={external_id}"
            )

        # 6. Создаём или обновляем ExternalAccount
        if existing:
            # Привязываем к найденному контакту
            existing.contact_id = contact
            await existing.update()
            account = existing
        else:
            # Создаём новый
            account = ChatExternalAccount(
                name=display_name or contact_value or external_id,
                external_id=external_id,
                connector_id=connector,
                contact_id=contact,
                raw=raw,
            )
            account.id = await self.create(payload=account)

            logger.info(
                f"Created ChatExternalAccount {account.id} "
                f"linked to Contact {contact.id}"
            )

        return account, contact, created
