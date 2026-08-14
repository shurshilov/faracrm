# Copyright 2025 FARA CRM
# Chat Phone module - telephony number model
#
# Отдельная сущность «номер телефонии» — то, что НАСТРАИВАЕТСЯ в АТС/провайдере
# (extension/SIP, транк, ring group, очередь), в отличие от ChatExternalAccount
# (внешний аккаунт СОБЕСЕДНИКА в разговоре). Единая для всех телефонных
# провайдеров (Asterisk/FreePBX, Sipuni, Mango, …)
#
# Наполняется синхронизацией номеров (strategy.sync_numbers), матчит сотрудника
# (user_id) по его sip-контакту

from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Integer,
    Many2one,
    Selection,
    Text,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.core.enviroment import env
from backend.base.crm.users.audit_mixin import AuditMixin

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.project_setup import ChatConnector


class PhoneNumber(AuditMixin, DotModel):
    """Номер телефонии, настроенный в АТС/провайдере (extension/trunk/group/queue)."""

    __table__ = "phone_number"

    id: int = Integer(primary_key=True)

    name: str | None = Char(max_length=255, description="Название номера")

    # Идентификатор у провайдера
    # "SIP/301" (endpoint)
    # "group:3020" (ring group)
    # "queue:3000" (очередь).
    external_id: str = Char(
        max_length=255,
        required=True,
        description="ID у провайдера (уникален с connector_id)",
    )

    # Набираемый номер / линия (tel). Напр. "SIP/301", "3020".
    number: str | None = Char(
        max_length=128, description="Набираемый номер / линия"
    )

    # Внутренний номер (extension), напр. "301". Для trunk/group/queue — их номер.
    extension: str | None = Char(
        max_length=64, description="Extension / номер"
    )

    # Тип номера (унифицирован по провайдерам; у Asterisk = asterisk_type).
    kind: str = Selection(
        options=[
            ("number", "Номер / extension"),
            ("trunk", "Транк"),
            ("group", "Группа (ring group)"),
            ("queue", "Очередь"),
        ],
        default="number",
        description="Тип номера: extension / trunk / group / queue",
    )

    connector_id: "ChatConnector" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        required=True,
        ondelete="cascade",
        index=True,
        description="Коннектор-провайдер телефонии",
    )

    # Сотрудник-владелец линии (оператор). NULL у транков/групп/очередей и у
    # нераспознанных extension'ов (заполнить вручную).
    user_id: "User | None" = Many2one(
        relation_table=lambda: env.models.user,
        ondelete="set null",
        index=True,
        description="Сотрудник-оператор линии",
    )

    # Правила лидогенерации на этот номер (как у Odoo cloud.phone.number).
    lead_generation: str = Selection(
        options=[
            ("self", "Создавать лид (на оператора)"),
            ("common", "Создавать общий лид"),
            ("no", "Не создавать лид"),
        ],
        default="no",
        description="Лид при отвеченном звонке на этот номер",
    )
    lead_generation_missed: str = Selection(
        options=[
            ("self", "Создавать лид (на оператора)"),
            ("common", "Создавать общий лид"),
            ("no", "Не создавать лид"),
        ],
        default="no",
        description="Лид при пропущенном звонке на этот номер",
    )

    # Создавать ли партнёра по звонкам, где ЭТОТ номер — контрагент (клиент).
    create_partner: bool = Boolean(
        default=True,
        description="Создавать партнёра по звонкам с этим номером",
    )

    # Технические номера (транки/группы/очереди) можно игнорировать в истории.
    ignore: bool = Boolean(
        default=False,
        description="Игнорировать номер в истории звонков (технический)",
    )

    raw: str | None = Text(description="Сырые данные из которых создан номер")

    active: bool = Boolean(default=True)
    sequence: int = Integer(default=10, description="Порядок сортировки")

    async def find_by_external_id(
        self, external_id: str, connector_id: int
    ) -> "PhoneNumber | None":
        """Найти номер по external_id + коннектору (ключ upsert синхронизации)."""
        rows = await self.search(
            filter=[
                ("external_id", "=", external_id),
                ("connector_id", "=", connector_id),
            ],
            fields=["id"],
            limit=1,
        )
        return rows[0] if rows else None

    @classmethod
    async def find_by_number(cls, connector_id: int, value: str | None):
        """
        Наш номер у коннектора по extension ИЛИ number (сравнение по цифрам).

        По нему решаем «это наш номер (внутренний) или внешний клиент»: результат
        не None ⇒ номер наш. Используется и попапом ARI (клиент = НЕ наш номер),
        и пайплайном (контрагент — наш номер с create_partner=False → внутренний).
        """
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        if not digits:
            return None
        rows = await env.models.phone_number.search(
            filter=[
                [("extension", "=", digits), "or", ("number", "=", digits)],
                "and",
                ("connector_id", "=", connector_id),
            ],
            fields=["id", "user_id", "create_partner"],
            fields_nested={"user_id": ["id"]},
            limit=1,
        )
        return rows[0] if rows else None

    @staticmethod
    def _apply_operator_default(payload, assigned) -> None:
        """
        Операторская линия (есть extension И привязан сотрудник) → по умолчанию
        НЕ создавать партнёра (create_partner=False): звонки с неё — внутренние.
        Уважаем явную установку: если create_partner передан в payload — не трогаем.
        """
        if "create_partner" in assigned:
            return
        if payload.extension and payload.user_id:
            payload.create_partner = False

    @hybridmethod
    async def create(self, payload, session=None, depends_jobs=None) -> int:
        PhoneNumber._apply_operator_default(payload, payload.assigned_fields())
        return await super().create(payload, session, depends_jobs)

    async def update(
        self, payload, fields=None, session=None, depends_jobs=None
    ):
        PhoneNumber._apply_operator_default(
            payload, fields or payload.assigned_fields()
        )
        return await super().update(payload, fields, session, depends_jobs)
