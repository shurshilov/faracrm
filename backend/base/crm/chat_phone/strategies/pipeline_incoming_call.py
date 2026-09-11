# Copyright 2025 FARA CRM
# Chat Phone module - incoming CALL pipeline (Архитектура 2)
#
# Звонок — входящее событие, но БЕЗ chat_message. Наследуем message-пайплайн и
# ПЕРЕИСПОЛЬЗУЕМ его резолв клиент→партнёр→лид (телефонный адаптер реализует
# интерфейс ChatMessageAdapter: author_id/author_name/text/chat_id), а отличия
# звонка делаем своими шагами:
#   • внутренний звонок (обе ноги — наши линии) партнёра/лид НЕ заводит;
#   • чат/сообщение/WS не создаём — пишем строку в call (upsert по uniqueid) +
#     аудиозапись (res_model='call') и показываем живую карточку (CallCard);
#   • резолвим ДВЕ ноги → наша линия (phone_number_id), направление, is_internal.

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from backend.base.crm.chat.strategies.pipeline_incoming import (
    IncomingMessage,
    IncomingMessagePipeline,
)
from backend.base.crm.chat_phone.call_card import CallCard

if TYPE_CHECKING:
    from backend.base.crm.chat_phone.models.call import Call
    from .adapter import PhoneMessageAdapter

logger = logging.getLogger(__name__)

# Ссылки на фоновые задачи записи — на уровне модуля: asyncio держит только
# слабые, а пайплайн живёт лишь на время события.
_recording_tasks: "set[asyncio.Task]" = set()


class IncomingCallPipeline(IncomingMessagePipeline):
    """
    Пайплайн СОБЫТИЯ ЗВОНКА поверх message-пайплайна.

    Что делать с событием, решается ЗДЕСЬ (стратегия — только транспорт):
      * answered → показать карточку тому, чья линия ответила; в реестр не пишем
        (данных о звонке ещё нет);
      * ended    → убрать карточку и записать звонок: _resolve_legs →
        (клиентский? _resolve_counterparty / _resolve_contact / _attach_lead —
        шаги базового класса) → _persist_call;
      * прочее (дозвон, служебные события) → ничего.

    Роутинг в чат, создание сообщения и WS-нотификацию НЕ выполняем.
    """

    def __init__(
        self,
        strategy,
        env,
        connector,
        adapter,
        notify_card=True,
        generate_lead=True,
    ):
        # notify=False: в чат ничего не шлём — у звонка своя карточка (CallCard).
        super().__init__(
            strategy,
            env,
            connector,
            adapter,
            notify=False,
            generate_lead=generate_lead,
        )
        self.notify_card = notify_card
        self.call: "Call | None" = None

    async def run(self) -> "Call | None":
        ctx = self.ctx
        await ctx.strategy.log_event(ctx.connector, ctx.env, ctx.adapter)

        event = ctx.adapter.event_type
        if event not in ("answered", "ended"):
            return None  # дозвон и служебные события звонка

        # Номера сотрудников (резолв «наш/клиент») нужны только с этого момента:
        # на служебных событиях — а их у ARI большинство — в БД не ходим.
        await ctx.adapter.cache_numbers(ctx.env)
        # Ноги считаем ОДИН раз и до ветвления: и карточке, и записи нужны одни
        # и те же факты — наша линия, её сотрудник, направление, клиент.
        await self._resolve_legs()

        if event == "answered":
            await self._show_card()
            return None

        await self._hide_card()
        for adapter in await self._final_adapters():
            await self._save_call(adapter)
        return self.call

    # ==================== живая карточка ====================

    async def _show_card(self) -> None:
        """
        Карточка сотруднику, чья линия ответила.

        Клиента резолвим ТОЛЬКО ЧТЕНИЕМ: партнёра и лид заводит запись звонка на
        'ended' — внутри транзакции и когда звонок точно состоялся. Незнакомый
        номер показываем как есть. Косметика не должна ронять обработку события,
        поэтому ошибки гасим здесь, а не общим except стратегии.
        """
        if not self.notify_card:
            return
        if self._is_internal:
            return  # сотрудник↔сотрудник: клиента нет
        if not (self._our_user_id and self._client_number):
            # Иначе «попап не пришёл» не отличить от «попап не показывали».
            logger.info(
                "[%s] карточка не показана: линия=%s сотрудник=%s клиент=%r",
                self.ctx.strategy.strategy_type,
                self._phone_number_id,
                self._our_user_id,
                self._client_number,
            )
            return

        ctx = self.ctx
        number = ctx.adapter.normalize_phone(self._client_number)
        try:
            name, partner_id, lead_id = await self._lookup_client(number)
            await CallCard.show(
                ctx.env,
                self._our_user_id,
                {
                    "number": number,
                    "name": name or number,
                    "direction": self._direction,
                    "disposition": "answered",
                    "partner_id": partner_id,
                    "lead_id": lead_id,
                    "connector_type": ctx.connector.type,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] call card show failed: %s",
                ctx.strategy.strategy_type,
                exc,
            )

    async def _hide_card(self) -> None:
        """Убрать карточку у того же сотрудника, которому её показали."""
        if not (
            self.notify_card and self._our_user_id and self._client_number
        ):
            return
        ctx = self.ctx
        try:
            await CallCard.hide(
                ctx.env,
                self._our_user_id,
                ctx.adapter.normalize_phone(self._client_number),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] call card hide failed: %s",
                ctx.strategy.strategy_type,
                exc,
            )

    async def _lookup_client(self, number: str):
        """Партнёр и его свежий лид по номеру — (имя, partner_id, lead_id)."""
        ctx = self.ctx
        if not ctx.connector.contact_type_id:
            return None, None, None
        contact = await ctx.env.models.contact.find_for_webhook(
            contact_type=ctx.connector.contact_type_id, value=number
        )
        if not (contact and contact.partner_id):
            return None, None, None
        lead = await ctx.env.models.lead.find_last_for_chat(
            contact.partner_id.id, ctx.connector.id
        )
        return (
            contact.partner_id.name,
            contact.partner_id.id,
            lead.id if lead else None,
        )

    # ==================== запись звонка ====================

    async def _final_adapters(self) -> list["PhoneMessageAdapter"]:
        """
        Записи с ПОЛНЫМИ данными звонка. Обычно завершающее событие само ими и
        является; Asterisk на ARI-хэнгапе данных не присылает и до-запрашивает
        CDR — что именно спросить, знает стратегия провайдера.
        """
        ctx = self.ctx
        records = await ctx.strategy.final_call_records(
            ctx.connector, ctx.env, ctx.adapter
        )
        if records is None:
            return [ctx.adapter]

        adapters = []
        for raw in records:
            adapter = ctx.strategy.create_message_adapter(ctx.connector, raw)
            if adapter.should_skip:
                continue
            await adapter.cache_numbers(ctx.env)
            adapters.append(adapter)
        return adapters

    async def _save_call(self, adapter: "PhoneMessageAdapter") -> None:
        """
        Запись ОДНОГО звонка: свой контекст, своя транзакция.

        Контекст на каждую запись новый: до-запрос может вернуть несколько строк
        (Asterisk отдаёт CDR по uniqueid ИЛИ linkedid), и клиент/лид предыдущей
        строки не должны протечь в следующую — у внутреннего звонка их нет вовсе.
        """
        base = self.ctx
        ctx = self.ctx = IncomingMessage(
            env=base.env,
            connector=base.connector,
            adapter=adapter,
            strategy=base.strategy,
        )
        self.call = None
        async with ctx.env.apps.db.get_transaction():
            # Ноги события уже посчитаны в run(); пересчитываем только у
            # до-запрошенных записей — у них они свои.
            if adapter is not base.adapter:
                await self._resolve_legs()
            # Клиентский звонок → тот же резолв клиента/партнёра/лида, что у
            # сообщений (шаги базового пайплайна). Внутренний (обе ноги — наши)
            # партнёра/лид не заводит: клиента нет.
            if not self._is_internal and await self._resolve_counterparty():
                await self._resolve_contact()
                if self.generate_lead:
                    await self._attach_lead()
            await self._persist_call()

        if self.call:
            self._schedule_recording(ctx, adapter, self.call)

    def _schedule_recording(self, ctx, adapter, call) -> None:
        """
        Запись разговора — фоном: это скачивание у провайдера + заливка в
        хранилище, секунды, а событие звонка приходит webhook-запросом (у
        Asterisk-агента таймаут 5 с, и события он читает последовательно).
        Не доедет — до-качает следующий проход по этому звонку (крон/импорт).
        """
        task = asyncio.create_task(
            ctx.env.models.call._save_recording(
                ctx.env, ctx.connector, adapter, ctx.strategy, call
            ),
            name=f"call_recording_{call.id}",
        )
        _recording_tasks.add(task)
        task.add_done_callback(_recording_tasks.discard)

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
        # Сотрудник нашей линии — он же адресат карточки. Приходит тем же
        # запросом (find_by_number тянет user_id), отдельного не нужно.
        self._our_user_id = (
            our_line.user_id.id if (our_line and our_line.user_id) else None
        )
        self._is_internal = bool(caller_line and callee_line)
        # Клиент = ВНЕШНЯЯ нога, по уже вычисленному направлению: входящий →
        # звонящий (src), исходящий → вызываемый (dst).
        self._client_number = (
            ctx.adapter.caller_number
            if self._direction == "incoming"
            else ctx.adapter.callee_number
        )

    async def _resolve_counterparty(self) -> bool:
        """
        Клиент-контрагент — внешняя нога, посчитанная в _resolve_legs.

        Переопределяем базовый шаг (он берёт adapter.author_id через кэш
        сотрудников — для исходящего с транка/DID это дало бы наш же номер).
        Пусто → пропускаем резолв партнёра/лида.
        """
        if not self._client_number:
            return False
        ctx = self.ctx
        ctx.counterparty_external_id = self._client_number
        ctx.counterparty_external_name = self._client_number
        return True

    async def _persist_call(self) -> None:
        """Upsert строки call по (connector, uniqueid). Запись — после коммита."""
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

        existing = await Call.search_one(
            filter=[
                ("connector_id", "=", ctx.connector.id),
                ("uniqueid", "=", uid),
            ],
            fields=["id"],
        )
        # Полный payload в обеих ветках: из БД строка приходит только с id, а
        # имени файла записи и логу нужны направление, uniqueid и номера.
        if existing:
            await existing.update(Call(**payload))
            self.call = Call(**payload)
            self.call.id = existing.id
        else:
            self.call = Call(**payload)
            self.call.id = await Call.create(payload=self.call)

        # Одна строка на исход — как _log_route у сообщений: по ней видно судьбу
        # ЛЮБОГО звонка (у звонка своего _notify с логом нет).
        logger.info(
            "[%s] Call %s → id=%s (%s, internal=%s, line=%s, partner=%s, lead=%s)",
            ctx.strategy.strategy_type,
            uid,
            self.call.id,
            self._direction,
            self._is_internal,
            self._phone_number_id,
            partner.id if partner else None,
            ctx.lead_id,
        )
