# Copyright 2025 FARA CRM
# Contact model - contact data for partners and users

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Boolean,
    Datetime,
    Selection,
    Many2one,
    One2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.partners import Partner
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )


# Маппинг типов контактов на типы коннекторов
CONTACT_TYPE_CONNECTORS = {
    "phone": ["whatsapp", "viber", "sms"],
    "email": ["email"],
    "telegram": ["telegram"],
    "avito": ["avito"],
    "vk": ["vk"],
    "instagram": ["instagram"],
}

# Настройки типов контактов для фронтенда
CONTACT_TYPE_CONFIG = {
    "phone": {
        "label": "Телефон",
        "icon": "phone",
        "placeholder": "+7 999 123-45-67",
        "pattern": r"^[\+]?[0-9\s\-\(\)]{10,20}$",
        "sequence": 1,
    },
    "email": {
        "label": "Email",
        "icon": "mail",
        "placeholder": "example@mail.com",
        "pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
        "sequence": 2,
    },
    "telegram": {
        "label": "Telegram",
        "icon": "send",  # lucide icon
        "placeholder": "@username",
        "pattern": r"^@?[a-zA-Z][a-zA-Z0-9_]{4,31}$",
        "sequence": 3,
    },
    "avito": {
        "label": "Avito",
        "icon": "shopping-bag",
        "placeholder": "ID пользователя",
        "pattern": r"^\d+$",
        "sequence": 4,
    },
    "vk": {
        "label": "ВКонтакте",
        "icon": "message-circle",
        "placeholder": "vk.com/username",
        "pattern": r"^(vk\.com\/)?[a-zA-Z0-9_\.]+$",
        "sequence": 5,
    },
    "instagram": {
        "label": "Instagram",
        "icon": "camera",
        "placeholder": "@username",
        "pattern": r"^@?[a-zA-Z0-9_\.]{1,30}$",
        "sequence": 6,
    },
}


class Contact(DotModel):
    """
    Контакт партнёра или пользователя.

    Хранит контактные данные:
    - Телефоны
    - Email адреса
    - Telegram username
    - И другие идентификаторы

    Одна запись = один контакт. У партнёра/пользователя может быть
    несколько записей разных типов.

    ChatExternalAccount ссылается на Contact для интеграции с мессенджерами.
    """

    __table__ = "contact"

    id: int = Integer(primary_key=True)

    # Значение контакта (телефон, email, username)
    # Используется name для совместимости с ORM (отображение в связях)
    name: str = Char(
        max_length=255,
        required=True,
        description="Значение: +79991234567, ivan@mail.ru, @username",
    )

    # Владелец контакта (один из двух должен быть заполнен)
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

    # Тип контакта
    contact_type: str = Selection(
        options=[
            ("phone", "Телефон"),
            ("email", "Email"),
            ("telegram", "Telegram"),
            ("avito", "Avito"),
            ("vk", "ВКонтакте"),
            ("instagram", "Instagram"),
        ],
        required=True,
        description="Тип контакта",
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

    # ==================== Properties ====================

    @property
    def connector_types(self) -> list[str]:
        """Получить типы коннекторов для данного типа контакта."""
        return CONTACT_TYPE_CONNECTORS.get(self.contact_type, [])

    @property
    def config(self) -> dict:
        """Получить конфиг типа контакта (label, icon, pattern, placeholder)."""
        return CONTACT_TYPE_CONFIG.get(self.contact_type, {})

    # ==================== Class Methods ====================

    @classmethod
    def get_connector_types_for_contact(cls, contact_type: str) -> list[str]:
        """Получить типы коннекторов для типа контакта."""
        return CONTACT_TYPE_CONNECTORS.get(contact_type, [])

    @classmethod
    def get_contact_type_for_connector(cls, connector_type: str) -> str | None:
        """Получить тип контакта для типа коннектора."""
        for contact_type, connectors in CONTACT_TYPE_CONNECTORS.items():
            if connector_type in connectors:
                return contact_type
        return None

    @classmethod
    def get_all_contact_configs(cls) -> dict:
        """Получить конфиги всех типов контактов (для API)."""
        return CONTACT_TYPE_CONFIG

    @classmethod
    def detect_contact_type(cls, value: str) -> str | None:
        """
        Автоопределение типа контакта по значению.

        Args:
            value: Значение для определения (+79991234567, ivan@mail.ru, @username)

        Returns:
            Тип контакта или None если не удалось определить
        """
        import re

        value = value.strip()

        # Сортируем по sequence для приоритета
        sorted_configs = sorted(
            CONTACT_TYPE_CONFIG.items(), key=lambda x: x[1].get("sequence", 99)
        )

        for contact_type, config in sorted_configs:
            pattern = config.get("pattern")
            if pattern:
                try:
                    if re.match(pattern, value):
                        return contact_type
                except re.error:
                    continue

        return None

    # ==================== Instance Methods ====================

    async def get_partner_contacts(self, partner_id: int):
        """Получить все контакты партнёра."""
        return await self.search(
            filter=[
                ("partner_id", "=", partner_id),
                ("active", "=", True),
            ],
            sort="contact_type",
        )

    async def get_user_contacts(self, user_id: int):
        """Получить все контакты пользователя."""
        return await self.search(
            filter=[
                ("user_id", "=", user_id),
                ("active", "=", True),
            ],
            sort="contact_type",
        )

    async def find_by_name(
        self,
        name: str,
        contact_type: str | None = None,
        partner_id: int | None = None,
        user_id: int | None = None,
    ) -> "Contact | None":
        """
        Найти контакт по значению (name).

        Args:
            name: Значение для поиска (+79991234567, @username)
            contact_type: Фильтр по типу контакта
            partner_id: Фильтр по партнёру
            user_id: Фильтр по пользователю
        """
        filter_conditions = [
            ("name", "=", name),
            ("active", "=", True),
        ]

        if contact_type:
            filter_conditions.append(("contact_type", "=", contact_type))
        if partner_id:
            filter_conditions.append(("partner_id", "=", partner_id))
        if user_id:
            filter_conditions.append(("user_id", "=", user_id))

        results = await self.search(
            filter=filter_conditions,
            limit=1,
        )

        return results[0] if results else None
