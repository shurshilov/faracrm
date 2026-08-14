# Copyright 2025 FARA CRM
# Chat Phone Asterisk - журнал телефонии (экран «События»)
#
# «Журнал Asterisk»: каждая ЗАПИСЬ = одно событие телефонии:
#   - kind='ari_event' — ARI-событие, принятое слушателем (in-process WS в local
#     или webhook от агента в remote). Пишется в strategy._process_ari — то есть
#     ровно то, что реально прилетело по ARI (после фильтрации events_used).
#   - kind='cdr_read'  — факт чтения CDR из БД АТС (сколько строк, за какое окно
#     / по какому uniqueid). Пишется на cron-импорте истории и при добром CDR по
#     завершению звонка.
#
# Диагностический журнал: по нему видно, что происходит с телефонией, без доступа
# к серверу Asterisk. Пишется best-effort (см. AsteriskLog.record) — сбой записи
# журнала НИКОГДА не роняет обработку звонка.

import json
import logging
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
from backend.base.system.core.enviroment import env
from backend.base.crm.users.audit_mixin import AuditMixin

if TYPE_CHECKING:
    from backend.project_setup import ChatConnector

logger = logging.getLogger(__name__)


class AsteriskLog(AuditMixin, DotModel):
    """Журнал телефонии Asterisk: ARI-события и чтения CDR (экран «События»)."""

    __table__ = "asterisk_log"

    id: int = Integer(primary_key=True)

    # Краткая человекочитаемая метка (по умолчанию = note/event_type/kind).
    name: str | None = Char(
        max_length=255, description="Краткое описание записи"
    )

    connector_id: "ChatConnector | None" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        ondelete="set null",
        index=True,
        description="Коннектор телефонии",
    )

    kind: str = Selection(
        options=[
            ("ari_event", "ARI-событие"),
            ("cdr_read", "Чтение CDR"),
        ],
        default="ari_event",
        description="Тип записи журнала",
    )

    # Тип ARI-события (ChannelStateChange/ChannelDestroyed/…) или имя чтения CDR
    # (fetch_call_history / fetch_calls_by_id).
    event_type: str | None = Char(
        max_length=128,
        index=True,
        description="Тип ARI-события или метод чтения CDR",
    )

    # id/uniqueid канала звонка (если применимо) — для сшивки с историей.
    uniqueid: str | None = Char(
        max_length=128, index=True, description="uniqueid / id канала"
    )

    note: str | None = Char(
        max_length=512, description="Человекочитаемая сводка"
    )

    payload: str | None = Text(
        description="Сырое ARI-событие / параметры чтения (JSON)"
    )

    active: bool = Boolean(default=True)

    @classmethod
    async def record(
        cls,
        connector_id: int | None,
        kind: str,
        event_type: str | None = None,
        uniqueid: str | None = None,
        note: str | None = None,
        payload=None,
    ) -> None:
        body = None
        if payload is not None:
            try:
                body = json.dumps(payload, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                body = str(payload)

        label = (note or event_type or kind or "")[:255]
        await env.models.asterisk_log.create(
            payload=env.models.asterisk_log(
                name=label,
                connector_id=(
                    env.models.chat_connector(id=connector_id)
                    if connector_id
                    else None
                ),
                kind=kind,
                event_type=event_type,
                uniqueid=uniqueid,
                note=note,
                payload=body,
            )
        )
