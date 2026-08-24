# Copyright 2025 FARA CRM
# Chat Phone module - Call (независимый реестр звонков, Архитектура 2)
#
# Звонок — САМОСТОЯТЕЛЬНАЯ сущность, НЕ chat_message. Пишется ВСЕГДА (даже без
# привязки к клиенту/сотруднику — все связи nullable). Запись в БД делает
# IncomingCallPipeline (strategies/pipeline_incoming_call.py). Экран «Звонки»
# читает таблицу напрямую; в историю чата звонки подмешиваются на чтении как
# call_external (Call.list_for_chat → messages-роутер).

import logging
import mimetypes
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Integer,
    Many2one,
    Selection,
    Text,
    Datetime,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.users.audit_mixin import AuditMixin
from datetime import datetime

if TYPE_CHECKING:
    from backend.project_setup import ChatConnector
    from backend.base.crm.partners.models.partners import Partner
    from backend.base.crm.leads.models.leads import Lead
    from backend.base.crm.chat_phone.models.phone_number import PhoneNumber
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)

# Сигнатуры форматов записи, отличных от mp3 (он же — дефолт, см.
# Call._recording_mimetype).
AUDIO_SIGNATURES = ((b"RIFF", "audio/wav"), (b"OggS", "audio/ogg"))


class Call(AuditMixin, DotModel):
    """Звонок телефонии — независимый реестр (Архитектура 2)."""

    __table__ = "call"

    id: int = Integer(primary_key=True)

    connector_id: "ChatConnector" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        ondelete="cascade",
        index=True,
        description="Коннектор телефонии",
    )

    uniqueid: str = Char(
        max_length=128, index=True, description="uniqueid/linkedid"
    )

    # Направление есть у ЛЮБОГО звонка и выводится ОТ НАШЕЙ ЛИНИИ (подход Odoo
    # cloud_phone: «в астериске нет понятия входящий/исходящий» — оно вычисляется):
    # наш номер — ВЫЗЫВАЕМЫЙ (dst) → входящий, иначе наш номер — звонящий (src) →
    # исходящий. «Внутренний» (обе ноги наши) — отдельный признак is_internal,
    # направление у него тоже есть (входящий на вызываемого).
    direction: str = Selection(
        options=[
            ("incoming", "Входящий"),
            ("outgoing", "Исходящий"),
        ],
        default="incoming",
    )
    is_internal: bool = Boolean(
        default=False, description="Внутренний (сотрудник↔сотрудник)"
    )
    disposition: str = Selection(
        options=[
            ("answered", "Отвечен"),
            ("no_answer", "Пропущен"),
            ("busy", "Занято"),
            ("failed", "Ошибка"),
            ("cancelled", "Отменён"),
        ],
        default="answered",
    )

    number_from: str | None = Char(
        max_length=128, description="Номер, с которого звонили"
    )
    number_to: str | None = Char(
        max_length=128, description="Номер, на который звонили"
    )

    started_at: datetime | None = Datetime(description="Время звонка")
    duration: int = Integer(default=0, description="Длительность, сек")
    duration_talk: int = Integer(default=0, description="Разговор, сек")

    # Связи — ВСЕ опциональны (звонок пишется даже без привязки):
    # Наша линия (endpoint/транк/группа/очередь); оператор = phone_number.user_id.
    phone_number_id: "PhoneNumber" = Many2one(
        relation_table=lambda: env.models.phone_number,
        ondelete="set null",
        index=True,
        description="Наша линия телефонии",
    )
    partner_id: "Partner" = Many2one(
        relation_table=lambda: env.models.partner,
        ondelete="set null",
        index=True,
        description="Клиент (внешний звонок)",
    )
    lead_id: "Lead" = Many2one(
        relation_table=lambda: env.models.lead,
        ondelete="set null",
        description="Лид",
    )

    # Запись разговора всегда одна — держим ссылкой (её ставит
    # _save_recording), чтобы колонка «Запись» в обычном списке получала id
    # вложения без отдельного запроса.
    record_id: "Attachment" = Many2one(
        relation_table=lambda: env.models.attachment,
        ondelete="set null",
        description="Запись разговора",
    )

    raw: str | None = Text(description="Сырой CDR")
    active: bool = Boolean(default=True)

    # Запись звонка в БД (upsert по uniqueid) делает IncomingCallPipeline
    # (chat_phone/strategies/pipeline_incoming_call.py) — он же резолвит
    # клиента/партнёра/лида, переиспользуя шаги message-пайплайна. Модель держит
    # только чтение (list_for_chat) и вложение записи (_save_recording).

    @classmethod
    async def list_for_chat(
        cls, env, chat_id: int, time_from=None, limit: int = 50
    ) -> list[dict]:
        """
        Звонки чата как виртуальные сообщения `call_external` (Архитектура 2).

        Подмешиваем звонки ПАРТНЁРА чата (chat_member.partner_id → звонки с этим
        partner_id). Внутренние звонки в чат не подмешиваются — они видны на
        экране «Звонки» (is_internal).

        time_from (ISO) — нижняя граница по времени: выравнивает выборку с окном
        уже загруженных сообщений. Виртуальный id = -call.id, чтобы не
        пересекаться с id реальных сообщений (фронт-дедуп) и не участвовать в
        пагинации. Форму держим совместимой с ChatMessage.serialize_for_chat.
        """
        session = env.apps.db.get_session()
        members = await session.execute(
            "SELECT partner_id FROM chat_member WHERE chat_id = %s "
            "AND partner_id IS NOT NULL AND is_active = true LIMIT 1",
            [chat_id],
        )
        if not members:
            return []
        partner_id = members[0]["partner_id"]

        where = ["c.active = true", "c.partner_id = %s"]
        params: list = [partner_id]
        if time_from:
            where.append("c.started_at >= %s")
            params.append(time_from)
        params.append(limit)

        rows = await session.execute(
            f"""
            SELECT
                c.id, c.direction, c.disposition,
                c.number_from, c.number_to,
                c.started_at, c.duration, c.duration_talk,
                c.partner_id, c.connector_id,
                cc.type AS connector_type,
                p.name AS partner_name,
                a.id AS att_id, a.name AS att_name, a.mimetype AS att_mimetype,
                a.size AS att_size, a.checksum AS att_checksum,
                a.is_voice AS att_is_voice, a.show_preview AS att_show_preview
            FROM "call" c
            JOIN chat_connector cc ON cc.id = c.connector_id
            LEFT JOIN partners p ON p.id = c.partner_id
            LEFT JOIN attachments a ON a.id = c.record_id
            WHERE {" AND ".join(where)}
            ORDER BY c.started_at DESC
            LIMIT %s
            """,
            params,
        )

        result: list[dict] = []
        for r in rows:
            # Номер клиента = нога, противоположная нашей (по направлению).
            client_number = (
                r["number_from"]
                if r["direction"] == "incoming"
                else r["number_to"]
            )
            author = {
                "id": r["partner_id"],
                "name": r["partner_name"] or client_number or "",
                "type": "partner",
            }

            attachments = []
            if r["att_id"]:
                attachments.append(
                    {
                        "id": r["att_id"],
                        "name": r["att_name"],
                        "mimetype": r["att_mimetype"],
                        "size": r["att_size"],
                        "checksum": r["att_checksum"],
                        "is_voice": r["att_is_voice"] or False,
                        "show_preview": r["att_show_preview"],
                    }
                )

            started = r["started_at"]
            result.append(
                {
                    "id": -r["id"],
                    "body": "",
                    "message_type": "call_external",
                    "create_datetime": (
                        started.isoformat() if started else None
                    ),
                    "starred": False,
                    "pinned": False,
                    "is_edited": False,
                    "is_read": True,
                    "parent_id": None,
                    "connector_id": r["connector_id"],
                    "connector_type": r["connector_type"],
                    "author": author,
                    "attachments": attachments,
                    "reactions": [],
                    "is_deleted": False,
                    # call_* поля для CallMessageContent (как у WebRTC-звонков)
                    "call_direction": r["direction"],
                    "call_disposition": r["disposition"],
                    "call_duration": r["duration"],
                    "call_talk_duration": r["duration_talk"],
                    "call_answer_time": None,
                    "call_end_time": None,
                }
            )
        return result

    @staticmethod
    async def _link_record(env, call_id: int, attachment_id: int) -> None:
        """Проставить звонку ссылку на запись (идемпотентно)."""
        Call = env.models.call
        attachment = env.models.attachment(id=attachment_id)
        await Call(id=call_id).update(Call(record_id=attachment))

    @staticmethod
    def _recording_mimetype(content: bytes) -> str:
        """
        Формат записи — по сигнатуре СОДЕРЖИМОГО: FreePBX пишет wav, облачные
        АТС mp3, а имя файла бывает без расширения. Неверный Content-Type ломает
        воспроизведение в браузере (скачанный файл при этом играет — плеер ОС
        определяет формат сам). Всё неопознанное считаем mp3, как раньше.
        """
        for signature, mimetype in AUDIO_SIGNATURES:
            if content.startswith(signature):
                return mimetype
        return "audio/mpeg"

    @staticmethod
    def _recording_name(call: "Call", ext: str) -> str:
        """Имя записи: кто кому звонил видно прямо в списке вложений."""
        if call.direction == "incoming":
            our, other = call.number_to, call.number_from
        else:
            our, other = call.number_from, call.number_to
        return f"call_{call.uniqueid}_{call.direction}_{our or ''}_{other or ''}{ext}"

    @staticmethod
    async def _save_recording(
        env, connector, adapter, strategy, call: "Call"
    ) -> None:
        """Скачать запись и прикрепить к звонку (res_model='call'), идемпотентно."""
        call_id = call.id
        rec_name = getattr(adapter, "recording_filename", None)
        if not adapter.call_record_url:
            # Отличаем «провайдер не отдаёт поле» от «АТС не писала разговор»:
            # по одному recordingfile=None это неразличимо.
            raw = getattr(adapter, "raw", None) or {}
            logger.info(
                "[call %s] запись не качаем: recordingfile=%r (поле у провайдера:"
                " %s), talk=%r",
                call_id,
                rec_name,
                "есть" if "recordingfile" in raw else "НЕТ",
                getattr(adapter, "talk_duration", None),
            )
            return
        existing = await env.models.attachment.search(
            filter=[("res_model", "=", "call"), ("res_id", "=", call_id)],
            fields=["id"],
            limit=1,
        )
        if existing:
            # Вложение уже есть — только дотягиваем ссылку (звонки, записанные
            # до появления record_id, иначе остались бы без кнопки «Запись»).
            await Call._link_record(env, call_id, existing[0].id)
            return
        try:
            content = await strategy._download_call_record(connector, adapter)
            if not content:
                # recordingfile есть, но байт нет: агент не нашёл файл (неверный
                # path_recordings у агента) или запись ещё не сброшена на диск.
                logger.warning(
                    "[call %s] запись %r: скачано 0 байт (агент не нашёл файл?)",
                    call_id,
                    rec_name,
                )
                return
            mimetype = Call._recording_mimetype(content)
            ext = mimetypes.guess_extension(mimetype) or ".mp3"
            attachment = env.models.attachment(
                name=Call._recording_name(call, ext),
                mimetype=mimetype,
                res_id=call_id,
                res_model="call",
                is_voice=True,
                content=content,
            )
            attachment_id = await env.models.attachment.create(
                payload=attachment
            )
            await Call._link_record(env, call_id, attachment_id)
            logger.info(
                "[call %s] запись %r сохранена как %s (%d байт)",
                call_id,
                rec_name,
                mimetype,
                len(content),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[call %s] record save failed: %s", call_id, exc)
