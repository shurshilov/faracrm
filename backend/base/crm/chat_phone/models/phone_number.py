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

import json
import logging
from datetime import datetime, timedelta
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

logger = logging.getLogger(__name__)


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

    # Пароль SIP-регистрации для звонилки в браузере. Обычное поле: правится
    # на форме номера виджетом пароля (widget="password"), владельцу линии
    # уезжает в /telephony/sip/config. Учтите, что раз поле не private, оно
    # видно всем, у кого есть доступ на чтение phone_number.
    sip_password: str | None = Char(
        max_length=128, description="Пароль SIP-регистрации"
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

    @classmethod
    async def find_by_external_id(
        cls, external_id: str, connector_id: int
    ) -> "PhoneNumber | None":
        """Найти номер по external_id + коннектору (ключ upsert синхронизации)."""
        rows = await env.models.phone_number.search(
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

    # ==================== cron-точки телефонии ====================
    # Реализация прямо здесь (методы модели), вызываются cron'ом по имени.
    # Провайдер приходит в strategy_type из kwargs задачи; env — глобальный
    # синглтон, как везде в коде.

    @classmethod
    async def _cron_connectors(cls, strategy_type):
        """Активные коннекторы типа — как их грузит webhook-роутер
        (contact_type_id нужен резолву клиента, иначе импорт не заведёт
        партнёра)."""
        return await env.models.chat_connector.search(
            filter=[("type", "=", strategy_type), ("active", "=", True)],
            fields_nested={
                "contact_type_id": ["id", "name", "is_phone_format"]
            },
        )

    @classmethod
    async def cron_fetch_call_history(cls, strategy_type=None) -> dict:
        """Cron: бэкофилл истории звонков за последнее окно — тихо (без карточек
        и лидов): живой звонок ведёт webhook-поток, дубли гасит upsert по
        uniqueid."""
        total = 0
        connectors = await cls._cron_connectors(strategy_type)
        for connector in connectors:
            strategy = connector.strategy
            end = datetime.now() - timedelta(
                minutes=strategy.HISTORY_WAIT_MINUTES
            )
            start = end - timedelta(minutes=strategy.HISTORY_WINDOW_MINUTES)
            try:
                result = await strategy.import_history(
                    connector, start.astimezone(), end.astimezone(), env
                )
                total += result.get("imported", 0)
            except Exception as e:  # noqa: BLE001
                logger.error("[%s] cron history failed: %s", strategy_type, e)

        logger.info(
            "[%s] cron imported %s calls from %s connectors",
            strategy_type,
            total,
            len(connectors),
        )
        return {"connectors": len(connectors), "calls": total}

    @classmethod
    async def cron_sync_numbers(cls, strategy_type=None) -> dict:
        """Cron: периодическая синхронизация номеров (то же, что кнопка в форме)."""
        total = 0
        connectors = await cls._cron_connectors(strategy_type)
        for connector in connectors:
            try:
                result = await connector.strategy.sync_numbers(connector, env)
                total += (result.get("details") or {}).get("synced", 0)
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "[%s] cron sync_numbers failed: %s", strategy_type, e
                )

        logger.info(
            "[%s] cron synced numbers for %s connectors (%s lines)",
            strategy_type,
            len(connectors),
            total,
        )
        return {"connectors": len(connectors), "lines": total}

    # ==================== синхронизация с провайдером ====================

    @classmethod
    async def sync_from_provider(
        cls, env, connector: "ChatConnector", records: list[dict]
    ) -> dict:
        """
        Наполнить реестр номерами провайдера (кнопка/крон «Синхронизировать»).

        records — линии в унифицированном виде (что именно спросить у провайдера,
        знает его стратегия; см. PhoneStrategyBase.fetch_numbers):
        {external_id, kind, number, extension, name, user_key, raw}.

        Возвращает {"ok", "message", "details": {"synced", "linked"}}.
        """
        synced = 0
        linked = 0
        async with env.apps.db.get_transaction():
            for rec in records:
                if not rec.get("external_id"):
                    continue
                user_id = await cls._resolve_owner(rec.get("user_key"))
                await cls._upsert_from_record(env, connector, rec, user_id)
                synced += 1
                if user_id:
                    linked += 1

        return {
            "ok": True,
            "message": (
                f"Синхронизировано номеров: {synced} "
                f"(привязано к сотрудникам: {linked})"
            ),
            "details": {"synced": synced, "linked": linked},
        }

    @classmethod
    async def _resolve_owner(cls, value: str | None) -> int | None:
        """
        Сотрудник-владелец линии по ЛЮБОМУ его контакту с таким значением.

        Тип контакта не фиксируем: у Asterisk линия сотрудника обычно заведена
        как sip-extension, у Sipuni/МегаФона это может быть просто номер
        (телефон) — важно совпадение значения, а не то, в какой графе оно лежит.
        Канонизация одинаковая: «301» остаётся как есть, телефон → E.164. Поиск
        идёт только по контактам СОТРУДНИКОВ (user_id задан), клиентские в
        выборку не попадают. Транк/группа/очередь/неизвестный номер → None.
        """
        if not value:
            return None
        contact = await env.models.contact.find_operator_by_value(value)
        user_id = contact.user_id.id if (contact and contact.user_id) else None
        # Диагностика привязки: видно, нашёлся ли контакт сотрудника с таким
        # номером и почему (контакт найден? user_id задан?).
        logger.info(
            "[phone_number] operator match: number=%r → contact_id=%s user_id=%s",
            value,
            contact.id if contact else None,
            user_id,
        )
        return user_id

    @classmethod
    async def _upsert_from_record(
        cls, env, connector: "ChatConnector", rec: dict, user_id: int | None
    ) -> None:
        """
        Создать/обновить номер по (connector_id, external_id).

        user_id (если найден сотрудник) проставляем; без матча привязку НЕ
        трогаем (ручную не затираем). number/extension/name — идентификация.
        """
        external_id = rec["external_id"]
        payload = dict(
            kind=rec.get("kind") or "number",
            number=rec.get("number"),
            extension=rec.get("extension"),
            raw=json.dumps(
                rec.get("raw") or {}, ensure_ascii=False, default=str
            ),
        )
        if user_id:
            payload["user_id"] = env.models.user(id=user_id)

        existing = await cls.find_by_external_id(external_id, connector.id)
        if existing:
            await existing.update(env.models.phone_number(**payload))
            return

        payload["name"] = rec.get("name") or rec.get("number") or external_id
        payload["external_id"] = external_id
        payload["connector_id"] = connector
        await env.models.phone_number.create(
            payload=env.models.phone_number(**payload)
        )

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
