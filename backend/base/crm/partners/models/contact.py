# Copyright 2025 FARA CRM
# Contact model - contact data for partners and users

from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Boolean,
    Many2one,
    One2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.users.audit_mixin import AuditMixin

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.partners import Partner
    from backend.base.crm.partners.models.contact_type import ContactType
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )


class Contact(AuditMixin, DotModel):
    """
    Контакт партнёра или пользователя.

    Хранит контактные данные: телефоны, email, telegram username, SIP-extension.
    Тип контакта — Many2one на contact_type.

    ВАЖНО (рефактор name→value):
    - value — РЕАЛЬНОЕ значение (+79991234567, ivan@mail.ru, @username, 307).
      Именно по нему идёт матчинг (find_for_webhook). Канонизируется на записи
      (email/username → lower; валидный телефон → E.164).
    - name — человекочитаемое ОПИСАНИЕ («Александр рабочий телефон»),
      опционально. Раньше в name лежало значение — переносится миграцией
      PartnersApp._migration_contact_name_to_value (удалить после переноса).
    """

    __table__ = "contact"

    id: int = Integer(primary_key=True)

    # Реальное значение контакта (по нему матчинг). Каноничное (см. _canonicalize).
    # НЕ required → nullable в БД. Причина: ADD COLUMN ... NOT NULL в уже
    # заполненную таблицу contact падает (NotNullViolation), а миграция,
    # заполняющая value, идёт позже (PartnersApp.post_init). На уровне ORM value
    # всегда задаётся при создании (find_or_create_for_webhook / create_with_partner).
    value: str | None = Char(
        index=True,
        description="Значение: +79991234567, ivan@mail.ru, @username, 307",
    )

    # Описание контакта. Историческая совместимость: раньше здесь лежало
    # ЗНАЧЕНИЕ, теперь основное значение — в value (миграция КОПИРУЕТ name→value,
    # name НЕ трогает). Остаётся NOT NULL (не меняем существующее ограничение БД);
    # со временем можно переиспользовать как «Александр рабочий телефон».
    name: str = Char(
        required=True,
        description="Описание контакта (для старых записей = значение)",
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
        description="Тип контакта (phone, sip, email, telegram, ...)",
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

    # ==================== Delegated Methods ====================

    @classmethod
    async def get_contact_type_id_for_connector(cls, connector_type: str):
        """Получить ID типа контакта для типа коннектора."""
        return await env.models.contact_type.get_contact_type_id_for_connector(
            connector_type
        )

    @staticmethod
    def _canonicalize(value: str) -> str:
        """
        Канонизировать значение контакта.

        - email / @username (есть '@') → lowercase (регистронезависимость по RFC);
        - валидный телефон → E.164 (+79991234567); 8/7/+7 сводятся к одному виду;
        - невалидные как телефон (SIP-extension «307», логины) — как есть.

        phonenumbers (libphonenumber) — проверенная нормализация. Регион по
        умолчанию RU (TODO: вынести в system_settings при мультирегионе).
        Если библиотека недоступна — деградируем без E.164 (телефон как есть).
        """
        v = value.strip()
        if "@" in v:
            return v.lower()
        try:
            import phonenumbers

            parsed = phonenumbers.parse(v, "RU")
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.E164
                )
        except Exception:
            pass
        return v

    @staticmethod
    def _canon_value(payload) -> None:
        """Канонизировать value ПРИ ЗАПИСИ (хранение каноничное → матч по '=')."""
        if isinstance(payload.value, str):
            payload.value = Contact._canonicalize(payload.value)

    @hybridmethod
    async def create(self, payload, session=None, depends_jobs=None) -> int:
        Contact._canon_value(payload)
        return await super().create(payload, session, depends_jobs)

    async def update(
        self, payload, fields=None, session=None, depends_jobs=None
    ):
        # Нормализуем только если поле value реально пишется.
        if "value" in (fields or payload.assigned_fields()):
            Contact._canon_value(payload)
        return await super().update(payload, fields, session, depends_jobs)

    @classmethod
    async def find_for_webhook(
        cls,
        contact_type: "ContactType",
        value: str | None,
    ) -> "Contact | None":
        """
        Найти активный КЛИЕНТСКИЙ контакт по значению внутри данного типа, либо
        — при is_phone_format — по любому телефонному типу (phone, whatsapp,
        viber, max используют один и тот же номер как идентификатор человека).

        GUARD: только контакты с partner_id (клиентские). Операторские линии
        (user_id задан, partner_id пуст: tel/extension операторов) в подбор
        собеседника НЕ попадают.
        """
        if not value:
            return None

        # Канонизируем вход так же, как хранение → индексируемый '=' матч.
        value = cls._canonicalize(value)

        # 1) Точное совпадение по типу (только клиентские контакты).
        exact = await env.models.contact.search(
            filter=[
                ("contact_type_id", "=", contact_type.id),
                ("value", "=", value),
                ("partner_id", "!=", None),
                ("active", "=", True),
            ],
            fields=["id", "value", "name", "user_id", "partner_id"],
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
            SELECT c.id, c.value, c.user_id, c.partner_id
            FROM contact c
            JOIN contact_type ct ON ct.id = c.contact_type_id
            WHERE ct.is_phone_format = true
              AND ct.active = true
              AND ct.id != %s
              AND c.value = %s
              AND c.partner_id IS NOT NULL
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
            value=row["value"],
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
    async def find_operator_by_value(
        cls,
        value: str | None,
        contact_type_id: int | None = None,
    ) -> "Contact | None":
        """
        Найти активный ОПЕРАТОРСКИЙ контакт по значению (user_id задан).

        Зеркало find_for_webhook, но для операторских линий телефонии: GUARD —
        только контакты с user_id (клиентские, с partner_id, сюда НЕ попадают).
        Используется синхронизацией номеров Asterisk: extension (sip) или телефон
        (phone) сотрудника → сам сотрудник (user_id).
        """
        if not value:
            return None

        # Канонизируем так же, как хранение (sip-extension остаётся как есть,
        # телефон → E.164) → индексируемый '=' матч.
        value = cls._canonicalize(value)

        filters = [
            ("value", "=", value),
            ("user_id", "!=", None),
            ("active", "=", True),
        ]
        if contact_type_id:
            filters.append(("contact_type_id", "=", contact_type_id))

        rows = await env.models.contact.search(
            filter=filters,
            fields=["id", "value", "name", "user_id", "contact_type_id"],
            fields_nested={"user_id": ["id", "name"]},
            limit=1,
        )
        return rows[0] if rows else None

    @classmethod
    async def create_with_partner(
        cls,
        contact_type: "ContactType",
        value: str,
        partner_name: str,
    ) -> "Contact":
        """
        Создать нового Partner и привязанный к нему Contact.

        Возвращает созданный Contact с заполненным id и ссылкой на Partner.
        name (описание) оставляем пустым — заполняется вручную позже.
        """
        partner = env.models.partner(name=partner_name)
        partner.id = await env.models.partner.create(payload=partner)

        contact = env.models.contact(
            user_id=None,
            partner_id=partner,
            contact_type_id=contact_type,
            value=value,
            # name NOT NULL → держим значение (совместимость); описание — потом
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

    async def find_by_value(
        self,
        value: str,
        contact_type_id: int | None = None,
        partner_id: int | None = None,
        user_id: int | None = None,
    ) -> "Contact | None":
        """Найти контакт по значению (value), опц. с фильтрами."""
        filter_conditions = [
            ("value", "=", self._canonicalize(value)),
            ("active", "=", True),
        ]

        if contact_type_id:
            filter_conditions.append(("contact_type_id", "=", contact_type_id))
        if partner_id:
            filter_conditions.append(("partner_id", "=", partner_id))
        if user_id:
            filter_conditions.append(("user_id", "=", user_id))

        results = await self.search(filter=filter_conditions, limit=1)
        return results[0] if results else None
