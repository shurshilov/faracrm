# Copyright 2025 FARA CRM
# Contact model - contact data for partners and users

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Boolean,
    Datetime,
    Many2one,
    One2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.partners import Partner
    from backend.base.crm.partners.models.contact_type import ContactType
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )


class Contact(DotModel):
    """
    Контакт партнёра или пользователя.

    Хранит контактные данные: телефоны, email, telegram username и т.д.
    Тип контакта — Many2one на contact_type.
    """

    __table__ = "contact"

    id: int = Integer(primary_key=True)

    # Значение контакта (телефон, email, username)
    name: str = Char(
        required=True,
        description="Значение: +79991234567, ivan@mail.ru, @username",
    )

    # Владелец контакта
    partner_id: "Partner | None" = Many2one(
        relation_table=lambda: env.models.partner,
        ondelete="cascade",
        description="Партнёр (клиент)",
        index=True,
    )
    user_id: "User | None" = Many2one(
        relation_table=lambda: env.models.user,
        ondelete="cascade",
        description="Пользователь",
        index=True,
    )

    # Тип контакта — FK на contact_type
    contact_type_id: "ContactType" = Many2one(
        relation_table=lambda: env.models.contact_type,
        ondelete="restrict",
        required=True,
        description="Тип контакта (phone, email, telegram, ...)",
        index=True,
    )

    # Внешние аккаунты привязанные к этому контакту
    external_account_ids: list["ChatExternalAccount"] = One2many(
        relation_table=lambda: env.models.chat_external_account,
        relation_table_field="contact_id",
        description="Внешние аккаунты (WhatsApp, Viber и т.д.)",
    )

    # Метаданные
    is_primary: bool = Boolean(
        default=False,
        description="Основной контакт данного типа",
    )
    active: bool = Boolean(default=True)

    # Временные метки
    create_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )
    write_date: datetime = Datetime(default=lambda: datetime.now(timezone.utc))

    # ==================== Delegated Methods ====================

    @classmethod
    async def get_contact_type_id_for_connector(cls, connector_type: str):
        """Получить ID типа контакта для типа коннектора."""
        return await env.models.contact_type.get_contact_type_id_for_connector(
            connector_type
        )

    @classmethod
    async def detect_contact_type(cls, value: str) -> str | None:
        """Автоопределение типа контакта по значению."""
        return await env.models.contact_type.detect_contact_type(value)

    @classmethod
    async def find_for_webhook(
        cls,
        contact_type: "ContactType",
        value: str | None,
    ) -> "Contact | None":
        """
        Найти активный контакт по значению внутри данного типа, либо —
        при is_phone_format — по любому телефонному типу (phone, whatsapp,
        viber используют один и тот же номер как идентификатор человека).
        """
        if not value:
            return None

        # 1) Точное совпадение по типу
        exact = await env.models.contact.search(
            filter=[
                ("contact_type_id", "=", contact_type.id),
                ("name", "=", value),
                ("active", "=", True),
            ],
            fields=["id", "name", "user_id", "partner_id"],
            limit=1,
        )
        if exact:
            return exact[0]

        # 2) Fallback по семейству телефонных типов — только если применимо
        if not contact_type.is_phone_format:
            return None

        session = env.apps.db.get_session()
        rows = await session.execute(
            """
            SELECT c.id, c.name, c.user_id, c.partner_id
            FROM contact c
            JOIN contact_type ct ON ct.id = c.contact_type_id
            WHERE ct.is_phone_format = true
              AND ct.active = true
              AND ct.id != %s
              AND c.name = %s
              AND c.active = true
            LIMIT 1
            """,
            (contact_type.id, value),
        )
        if not rows:
            return None

        row = rows[0]
        return env.models.contact(
            id=row["id"],
            name=row["name"],
            user_id=(
                env.models.user(id=row["user_id"])
                if row["user_id"] is not None
                else None
            ),
            partner_id=(
                env.models.partner(id=row["partner_id"])
                if row["partner_id"] is not None
                else None
            ),
        )

    @classmethod
    async def create_with_partner(
        cls,
        contact_type: "ContactType",
        value: str,
        partner_name: str,
    ) -> "Contact":
        """
        Создать нового Partner и привязанный к нему Contact.

        Удобство для сценариев, когда контакт появляется вместе с новым
        субъектом (например, входящий webhook от неизвестного отправителя).
        Возвращает созданный Contact с заполненным id и ссылкой на Partner.
        """
        partner = env.models.partner(name=partner_name)
        partner.id = await env.models.partner.create(payload=partner)

        contact = env.models.contact(
            user_id=None,
            partner_id=partner,
            contact_type_id=contact_type,
            name=value,
            is_primary=True,
        )
        contact.id = await env.models.contact.create(payload=contact)
        return contact

    # ==================== Instance Methods ====================

    async def get_partner_contacts(self, partner_id: int):
        """Получить все контакты партнёра."""
        return await self.search(
            filter=[
                ("partner_id", "=", partner_id),
                ("active", "=", True),
            ],
            sort="contact_type_id",
        )

    async def get_user_contacts(self, user_id: int):
        """Получить все контакты пользователя."""
        return await self.search(
            filter=[
                ("user_id", "=", user_id),
                ("active", "=", True),
            ],
            sort="contact_type_id",
        )

    async def find_by_name(
        self,
        name: str,
        contact_type_id: int | None = None,
        partner_id: int | None = None,
        user_id: int | None = None,
    ) -> "Contact | None":
        """Найти контакт по значению (name)."""
        filter_conditions = [
            ("name", "=", name),
            ("active", "=", True),
        ]

        if contact_type_id:
            filter_conditions.append(("contact_type_id", "=", contact_type_id))
        if partner_id:
            filter_conditions.append(("partner_id", "=", partner_id))
        if user_id:
            filter_conditions.append(("user_id", "=", user_id))

        results = await self.search(
            filter=filter_conditions,
            limit=1,
        )

        return results[0] if results else None
