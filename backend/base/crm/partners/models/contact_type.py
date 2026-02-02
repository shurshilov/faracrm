# Copyright 2025 FARA CRM
# ContactType model - reference table for contact types

from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Boolean,
    One2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector


class ContactType(DotModel):
    """
    Тип контакта (справочник).

    Хранит конфигурацию типов контактов:
    phone, email, telegram, whatsapp, viber, instagram, vk, website и т.д.

    Связь с коннекторами: chat_connector.contact_type_id → contact_type.id
    One2many connector_ids показывает какие коннекторы работают с этим типом.
    """

    __table__ = "contact_type"

    id: int = Integer(primary_key=True)

    # Код типа (уникальный: phone, email, telegram, ...)
    name: str = Char(
        max_length=50,
        required=True,
        description="Код типа (phone, email, telegram, ...)",
        index=True,
    )

    # Отображаемое название
    label: str = Char(
        max_length=100,
        required=True,
        description="Название для отображения",
    )

    # Иконка (tabler icon name)
    icon: str | None = Char(
        max_length=100,
        description="Имя иконки (IconPhone, IconMail, ...)",
    )

    # Цвет бейджа
    color: str = Char(
        max_length=30,
        default="gray",
        description="Цвет для отображения (green, blue, cyan, ...)",
    )

    # Placeholder для ввода
    placeholder: str | None = Char(
        max_length=255,
        description="Подсказка ввода (+7 999 123-45-67, @username, ...)",
    )

    # Регулярное выражение для валидации / автоопределения
    pattern: str | None = Char(
        max_length=500,
        description="Regex для валидации и автоопределения типа",
    )

    # Связь с коннекторами (One2many)
    # chat_connector.contact_type_id → contact_type.id
    connector_ids: list["ChatConnector"] = One2many(
        relation_table=lambda: env.models.chat_connector,
        relation_table_field="contact_type_id",
        description="Коннекторы, работающие с этим типом контакта",
    )

    # Порядок сортировки
    sequence: int = Integer(default=10, description="Порядок сортировки")

    active: bool = Boolean(default=True)

    # ==================== Helpers ====================

    @classmethod
    async def get_by_name(cls, name: str) -> "ContactType | None":
        """Найти тип контакта по коду (name)."""
        results = await cls.search(
            filter=[("name", "=", name), ("active", "=", True)],
            limit=1,
        )
        return results[0] if results else None

    @classmethod
    async def get_contact_type_id_for_connector(cls, connector_type: str):
        """
        Получить ID типа контакта для данного типа коннектора.
        """
        connectors = await env.models.chat_connector.search(
            filter=[
                ("type", "=", connector_type),
                ("active", "=", True),
            ],
            fields=["id", "contact_type_id"],
            limit=1,
        )
        if connectors and connectors[0].contact_type_id:
            return connectors[0].contact_type_id
        return None

    @classmethod
    async def detect_contact_type(cls, value: str) -> str | None:
        """
        Автоопределение типа контакта по значению.

        Проходит по всем типам (отсортированным по sequence),
        пробует regex pattern.
        """
        import re

        value = value.strip()
        all_types = await cls.search(
            filter=[("active", "=", True)],
            sort="sequence",
        )

        for ct in all_types:
            if ct.pattern:
                try:
                    if re.match(ct.pattern, value):
                        return ct.name
                except re.error:
                    continue

        return None


# Начальные данные для заполнения таблицы
INITIAL_CONTACT_TYPES = [
    {
        "name": "phone",
        "label": "Телефон",
        "icon": "IconPhone",
        "color": "green",
        "placeholder": "+7 999 123-45-67",
        "pattern": r"^[\+]?[0-9\s\-\(\)]{10,20}$",
        "sequence": 1,
    },
    {
        "name": "email",
        "label": "Email",
        "icon": "IconMail",
        "color": "blue",
        "placeholder": "example@mail.com",
        "pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
        "sequence": 2,
    },
    {
        "name": "telegram",
        "label": "Telegram",
        "icon": "IconBrandTelegram",
        "color": "cyan",
        "placeholder": "@username",
        "pattern": r"^@?[a-zA-Z][a-zA-Z0-9_]{4,31}$",
        "sequence": 3,
    },
    {
        "name": "whatsapp",
        "label": "WhatsApp",
        "icon": "IconBrandWhatsapp",
        "color": "teal",
        "placeholder": "+7 999 123-45-67",
        "pattern": None,
        "sequence": 4,
    },
    {
        "name": "viber",
        "label": "Viber",
        "icon": "IconMessageCircle",
        "color": "violet",
        "placeholder": "+7 999 123-45-67",
        "pattern": None,
        "sequence": 5,
    },
    {
        "name": "instagram",
        "label": "Instagram",
        "icon": "IconBrandInstagram",
        "color": "pink",
        "placeholder": "@username",
        "pattern": r"^@?[a-zA-Z0-9_\.]{1,30}$",
        "sequence": 6,
    },
    {
        "name": "vk",
        "label": "ВКонтакте",
        "icon": "IconMessageCircle",
        "color": "indigo",
        "placeholder": "vk.com/username",
        "pattern": r"^(vk\.com\/)?[a-zA-Z0-9_\.]+$",
        "sequence": 7,
    },
    {
        "name": "avito",
        "label": "Avito",
        "icon": "IconShoppingBag",
        "color": "orange",
        "placeholder": "ID пользователя",
        "pattern": r"^\d+$",
        "sequence": 8,
    },
    {
        "name": "website",
        "label": "Сайт",
        "icon": "IconWorld",
        "color": "indigo",
        "placeholder": "https://example.com",
        "pattern": r"^https?://",
        "sequence": 9,
    },
]
