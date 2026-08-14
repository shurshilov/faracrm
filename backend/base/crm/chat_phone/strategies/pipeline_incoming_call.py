# Copyright 2025 FARA CRM
# Chat Phone module - incoming CALL pipeline (Архитектура 2)
#
# Звонок — входящее событие, но БЕЗ chat_message. Наследуем message-пайплайн и
# ПЕРЕИСПОЛЬЗУЕМ его резолв клиент→партнёр→лид (телефонный адаптер реализует
# интерфейс ChatMessageAdapter: author_id/author_name/text/chat_id), а отличия
# звонка делаем своими шагами:
#   • внутренний звонок (обе ноги — наши линии) партнёра/лид НЕ заводит;
#   • чат/сообщение/WS не создаём — пишем строку в call (upsert по uniqueid) +
#     аудиозапись (res_model='call'); живой попап оператору идёт отдельно (ARI);
#   • резолвим ДВЕ ноги → наша линия (phone_number_id), направление, is_internal.

import json
import logging
from typing import TYPE_CHECKING

from backend.base.crm.chat.strategies.pipeline_incoming import (
    IncomingMessagePipeline,
)

if TYPE_CHECKING:
    from backend.base.crm.chat_phone.models.call import Call

logger = logging.getLogger(__name__)


class IncomingCallPipeline(IncomingMessagePipeline):
    """
    Пайплайн ВХОДЯЩЕГО ЗВОНКА поверх message-пайплайна.

    run(): _resolve_legs → (клиентский? _resolve_counterparty / _resolve_contact
    / _attach_lead — шаги базового класса) → _persist_call. Роутинг в чат,
    создание сообщения и WS-нотификацию НЕ выполняем.
    """

    def __init__(self, strategy, env, connector, adapter, generate_lead=True):
        # notify=False: в чат ничего не шлём (живой попап — отдельная ARI-карточка).
        super().__init__(
            strategy,
            env,
            connector,
            adapter,
            notify=False,
            generate_lead=generate_lead,
        )
        self.call: "Call | None" = None

    async def run(self) -> "Call | None":
        ctx = self.ctx
        # 1) Специфика звонка: наша линия, направление, внутренний ли.
        await self._resolve_legs()
        # 2) Клиентский звонок → тот же резолв клиента/партнёра/лида, что у
        #    сообщений (шаги базового пайплайна). Внутренний (обе ноги — наши)
        #    партнёра/лид не заводит: клиента нет.
        if not self._is_internal and await self._resolve_counterparty():
            await self._resolve_contact()
            if self.generate_lead:
                await self._attach_lead()
        # 3) Персистенс звонка (upsert по uniqueid) + запись.
        await self._persist_call()
        return self.call

    async def _resolve_legs(self) -> None:
        """
        Наша линия и направление — ОТ ЛИНИИ (как Odoo `_find_number_and_calltype`:
        «в астериске нет понятия входящий/исходящий» — направление выводится).

        Приоритет ВЫЗЫВАЕМОГО (dst): наш номер — вызываемый → ВХОДЯЩИЙ (линия =
        callee); иначе наш номер — звонящий (src) → ИСХОДЯЩИЙ (линия = caller);
        обе ноги чужие (транзит через АТС) → входящий, линии нет. Направление есть
        ВСЕГДА. Внутренний (обе ноги — наши линии) — отдельный признак is_internal;
        направление у него тоже есть (входящий на вызываемого).
        """
        ctx = self.ctx
        find = ctx.env.models.phone_number.find_by_number
        caller_line = await find(ctx.connector.id, ctx.adapter.caller_number)
        callee_line = await find(ctx.connector.id, ctx.adapter.callee_number)

        if callee_line:
            self._direction = "incoming"
            our_line = callee_line
        elif caller_line:
            self._direction = "outgoing"
            our_line = caller_line
        else:
            self._direction = "incoming"  # обе ноги чужие — транзит через АТС
            our_line = None

        self._phone_number_id = our_line.id if our_line else None
        self._is_internal = bool(caller_line and callee_line)

    async def _resolve_counterparty(self) -> bool:
        """
        Клиент = ВНЕШНЯЯ нога (та, что НЕ наша линия), по уже вычисленному
        направлению: входящий → звонящий (src), исходящий → вызываемый (dst).

        Переопределяем базовый шаг (он берёт adapter.author_id через кэш
        сотрудников — для исходящего с транка/DID это дало бы наш же номер).
        Пусто → пропускаем резолв партнёра/лида.
        """
        ctx = self.ctx
        client = (
            ctx.adapter.caller_number
            if self._direction == "incoming"
            else ctx.adapter.callee_number
        )
        if not client:
            return False
        ctx.counterparty_external_id = client
        ctx.counterparty_external_name = client
        return True

    async def _persist_call(self) -> None:
        """Upsert строки call по (connector, uniqueid) + аудиозапись."""
        ctx = self.ctx
        uid = ctx.adapter.message_id
        if not uid:
            return

        Call = ctx.env.models.call
        # ctx.contact есть только у клиентского звонка (внутренний его не резолвит).
        contact = getattr(ctx, "contact", None)
        partner = (
            contact.partner_id if (contact and contact.partner_id) else None
        )

        payload = dict(
            connector_id=ctx.connector,
            uniqueid=uid,
            direction=self._direction,
            is_internal=self._is_internal,
            disposition=ctx.adapter.disposition,
            number_from=ctx.adapter.caller_number or None,
            number_to=ctx.adapter.callee_number or None,
            started_at=ctx.adapter._timestamp_to_datetime(
                ctx.adapter.created_at
            ),
            duration=ctx.adapter.call_duration or 0,
            duration_talk=ctx.adapter.talk_duration or 0,
            phone_number_id=(
                ctx.env.models.phone_number(id=self._phone_number_id)
                if self._phone_number_id
                else None
            ),
            partner_id=partner,
            lead_id=(
                ctx.env.models.lead(id=ctx.lead_id) if ctx.lead_id else None
            ),
            raw=json.dumps(ctx.adapter.raw, ensure_ascii=False, default=str),
        )

        existing = await Call.search(
            filter=[
                ("connector_id", "=", ctx.connector.id),
                ("uniqueid", "=", uid),
            ],
            fields=["id"],
            limit=1,
        )
        if existing:
            self.call = existing[0]
            await self.call.update(Call(**payload))
        else:
            self.call = Call(**payload)
            self.call.id = await Call.create(payload=self.call)

        await Call._save_recording(
            ctx.env, ctx.connector, ctx.adapter, ctx.strategy, self.call.id
        )
