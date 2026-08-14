# Copyright 2025 FARA CRM
# Chat Phone Asterisk module - Asterisk / FreePBX strategy

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from backend.base.crm.chat_phone.strategies.strategy import PhoneStrategyBase
from .adapter import AsteriskPhoneAdapter

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.project_setup import ChatConnector

logger = logging.getLogger(__name__)

# Режимы импорта звонков из CDR → (слать WS-попап, генерировать лид).
# По умолчанию история идёт «silent»: создаём только сообщение звонка.
CDR_IMPORT_MODES = {
    "normal": (True, True),
    "no_notify": (False, True),
    "silent": (False, False),
}


class AsteriskPhoneStrategy(PhoneStrategyBase):
    """
    Стратегия Asterisk / FreePBX.

    Модель работы:
    - CDR — источник истины по звонку: запись пишется в независимый реестр call
      через IncomingCallPipeline (резолв клиента/партнёра/лида как у сообщений).
    - ARI-событие «hangup» → стратегия сразу до-запрашивает CDR по uniqueid и
      пишет звонок (near-real-time на завершении).
    - cron — фоновый бэкофилл истории за окно.

    Транспорт («откуда данные») выбирается КЛАССОМ-ИСТОЧНИКОМ (см. sources/),
    по полю connector.agent_mode:
    - remote (default): внешний Asterisk-agent — REST по connector_url (Basic-auth),
      ARI-события приходят на универсальный webhook FARA;
    - local: встроенный режим — CDR прямым SQL к БД Asterisk (пакет asterisk_agent),
      записи через ARI, ARI-события слушаются in-process (см. app.py). Конфиг —
      в типизированных колонках connector.asterisk_db_* / asterisk_ari_*.

    Обработку звонка (реестр call + партнёр/лид/запись) делает
    IncomingCallPipeline (см. PhoneStrategyBase.handle_webhook). Здесь — только
    транспорт (через источник) и ARI-роутинг/живой попап.
    """

    strategy_type = "phone_asterisk"
    TIMEOUT = 30.0
    HISTORY_WINDOW_MINUTES = 60
    HISTORY_WAIT_MINUTES = 1

    # ==================== источник данных ====================

    def _source(self, connector: "ChatConnector"):
        """Источник по connector.agent_mode: remote (REST) | local (SQL+ARI)."""
        from .sources import get_source

        return get_source(connector)

    # ==================== абстрактные методы ====================

    async def get_or_generate_token(self, connector: "ChatConnector"):
        return None

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        # local: внешний webhook НЕ нужен — ARI-события слушаются in-process
        # (постоянный WS-слушатель, см. app.py). Считаем настроенным сразу.
        if connector.agent_mode == "local":
            logger.info(
                "Asterisk local: ARI-события слушаются in-process, webhook не требуется"
            )
            return True
        # remote: пингуем внешний агент + напоминаем указать URL приёма ARI-событий
        try:
            await self._source(connector).list_numbers()
            logger.info(
                "Asterisk-agent доступен. Укажите в агенте URL ARI-событий: %s",
                connector.webhook_url,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Asterisk-agent проверка не удалась: %s", e)
        return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        return {"ok": True}

    async def test_connection(self, connector: "ChatConnector") -> dict:
        """Кнопка «Проверить соединение»: пинг списка номеров через источник."""
        try:
            numbers = await self._source(connector).list_numbers()
            count = len(numbers) if isinstance(numbers, list) else 0
            return {
                "ok": True,
                "message": f"Asterisk доступен. Номеров: {count}",
            }
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"Ошибка соединения: {e}"}

    async def set_listener(
        self, connector: "ChatConnector", enabled: bool, env: "Environment"
    ) -> dict:
        """
        Свич «Автозапуск ARI-слушателя» (local). enable — проверяем ARI и, только
        если прошло, персистим asterisk_ari_autostart=True и поднимаем слушатель
        СЕЙЧАС; disable — гасим слушатель и снимаем флаг. Если ARI не отвечает —
        не включаем (пользователь увидит ошибку, свич останется выключен).
        """
        app = env.apps.chat_phone_asterisk

        if not enabled:
            await connector.update(
                env.models.chat_connector(asterisk_ari_autostart=False)
            )
            await app.stop_listener(connector.id)
            return {
                "ok": True,
                "enabled": False,
                "message": "Автозапуск выключен, слушатель остановлен",
            }

        if connector.agent_mode != "local":
            return {
                "ok": False,
                "enabled": False,
                "message": "Автозапуск слушателя доступен только во встроенном (local) режиме",
            }

        # Проверка ARI (пинг списка номеров) — включаем ТОЛЬКО если прошло.
        test = await self.test_connection(connector)
        if not test.get("ok"):
            return {
                "ok": False,
                "enabled": False,
                "message": f"ARI недоступен, автозапуск не включён: {test.get('message')}",
            }

        await connector.update(
            env.models.chat_connector(asterisk_ari_autostart=True)
        )
        started = await app.ensure_listener(env, connector)
        return {
            "ok": True,
            "enabled": True,
            "message": (
                "Автозапуск включён, слушатель запущен"
                if started
                else "Автозапуск включён (слушатель поднимется на активном воркере)"
            ),
        }

    # ==================== синхронизация номеров ====================

    async def sync_numbers(
        self, connector: "ChatConnector", env: "Environment"
    ) -> dict:
        """
        Кнопка «Синхронизировать номера»
        - SIP-endpoints kind='number
        - ring groups kind='group'
        - queues → kind='queue'

        Ring groups/queues есть только во FreePBX.
        """
        source = self._source(connector)
        endpoints = await source.list_numbers()
        groups = await source.list_ring_groups()
        queues = await source.list_queues()

        synced = 0
        linked = 0
        async with env.apps.db.get_transaction():
            # на самом деле не всегда сип PJSIP, SIP, Local, IAX2, DAHDI, Dongle, WebRTC, WSS
            # но пока мы их принимаем за сип в срм, не разделяем это не важно
            sip_type = await env.models.contact_type.get_by_name("sip")

            for rec in endpoints:
                resource = rec.get("resource")
                if not resource:
                    continue
                user_id = await self._resolve_operator(env, resource, sip_type)
                await self._upsert_number(
                    env,
                    connector,
                    resource,
                    "number",
                    rec,
                    number=resource,
                    extension=resource,
                    user_id=user_id,
                    name=resource,
                )
                synced += 1
                if user_id:
                    linked += 1

            for rec in groups:
                grpnum = rec.get("grpnum")
                if not grpnum:
                    continue
                name = f"{rec.get('description') or grpnum}/{grpnum}"
                await self._upsert_number(
                    env,
                    connector,
                    f"group:{grpnum}",
                    "group",
                    rec,
                    number=f"{grpnum}",
                    extension=f"{grpnum}",
                    user_id=None,
                    name=name,
                )
                synced += 1

            for rec in queues:
                qext = rec.get("extension")
                if not qext:
                    continue
                name = f"{rec.get('descr') or qext}"
                await self._upsert_number(
                    env,
                    connector,
                    f"queue:{qext}",
                    "queue",
                    rec,
                    number=f"{qext}",
                    extension=f"{qext}",
                    user_id=None,
                    name=name,
                )
                synced += 1

        return {
            "ok": True,
            "message": (
                f"Синхронизировано номеров: {synced} "
                f"(привязано к сотрудникам: {linked})"
            ),
            "details": {"synced": synced, "linked": linked},
        }

    async def _upsert_number(
        self,
        env,
        connector,
        external_id,
        kind,
        raw_rec,
        number,
        extension,
        user_id,
        name,
    ):
        """
        Создать/обновить phone_number по (connector_id, external_id).

        user_id (если найден сотрудник) проставляем; без матча привязку НЕ трогаем
        (ручную не затираем). number/extension/name — идентификация номера.
        """
        payload = dict(
            kind=kind,
            number=number,
            extension=extension,
            raw=json.dumps(raw_rec, ensure_ascii=False),
        )
        if user_id:
            payload["user_id"] = env.models.user(id=user_id)

        existing = await env.models.phone_number.search(
            filter=[
                ("connector_id", "=", connector.id),
                ("external_id", "=", external_id),
            ],
            fields=["id"],
            limit=1,
        )
        if existing:
            await existing[0].update(env.models.phone_number(**payload))
        else:
            payload["name"] = name or number or external_id
            payload["external_id"] = external_id
            payload["connector_id"] = connector
            await env.models.phone_number.create(
                payload=env.models.phone_number(**payload)
            )

    async def _resolve_operator(self, env, resource, sip_type):
        """
        user_id сотрудника по его sip-контакту (value=resource; канонизация:
        extension «301» как есть, телефон → E.164). Транк/неизвестный → None.
        """
        contact = await env.models.contact.find_operator_by_value(
            resource, sip_type.id if sip_type else None
        )
        user_id = contact.user_id.id if (contact and contact.user_id) else None
        # Диагностика привязки: видно, нашёлся ли sip-контакт сотрудника с таким
        # extension и почему (тип найден? контакт найден? user_id задан?).
        logger.info(
            "[phone_asterisk] operator match: extension=%r sip_type_id=%s "
            "→ contact_id=%s user_id=%s",
            resource,
            sip_type.id if sip_type else None,
            contact.id if contact else None,
            user_id,
        )
        return user_id

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> AsteriskPhoneAdapter:
        return AsteriskPhoneAdapter(connector, raw_message)

    # ==================== приём webhook ====================

    async def handle_webhook(
        self,
        connector: "ChatConnector",
        payload: dict,
        env: "Environment",
        notify: bool = True,
        generate_lead: bool = True,
    ) -> Any:
        if not payload:
            return "OK"  # верификационный пустой POST от агента
        if self._is_ari_payload(payload):
            # Живой ARI-поток (звонок в реальном времени) — всегда обычный режим
            # (попап + лид). Флаги notify/generate_lead относятся к импорту CDR.
            return await self._process_ari(connector, payload, env)
        # CDR-запись → базовый handle_webhook → пайплайн (с учётом режима).
        return await super().handle_webhook(
            connector, payload, env, notify=notify, generate_lead=generate_lead
        )

    @staticmethod
    def _is_ari_payload(payload: dict) -> bool:
        return isinstance(payload.get("channel"), dict) and bool(
            payload.get("type")
        )

    async def _process_ari(
        self, connector: "ChatConnector", event: dict, env: "Environment"
    ) -> dict:
        """
        Живой ARI-поток (webhook агента ИЛИ in-process WS — формат одинаков).
        Всё разбирает АДАПТЕР (event_type / направление / клиент), здесь — только
        диспетчер:
        - answered → живой ПОПАП оператору (эфемерный, звонок в реестр НЕ пишем);
        - ended (ChannelDestroyed) → снять попап + до-запрос CDR по uniqueid →
          базовый handle_webhook (пишет звонок в реестр call + запись). Дубли
          гасит дедуп по uniqueid, несколько ChannelDestroyed звонка безопасны.

        Клиент = внешний номер (у внутреннего звонка сотрудник↔сотрудник клиента
        нет → адаптер даёт direction='internal' → попапа нет).
        """
        adapter = self.create_message_adapter(connector, event)
        etype = adapter.event_type  # answered / ended / progress (без БД)

        await env.models.asterisk_log.record(
            connector.id,
            "ari_event",
            event_type=event.get("type"),
            uniqueid=adapter.message_id,
            note=f"ARI {event.get('type')} → {etype}",
            payload=event,
        )
        if etype not in ("answered", "ended"):
            return {"ok": True}  # рабочий процесс звонка — игнорируем

        # Клиент нужен только для попапа; кэш номеров — только здесь (не на каждом
        # «progress»-событии). Внутренний звонок → client пустой → попапа нет.
        await adapter.cache_numbers(env)
        client = (
            "" if adapter.call_direction == "internal" else adapter.author_id
        )

        if etype == "answered":
            if client:
                await self._send_call_card(connector, env, client)
            return {"ok": True}

        # ended: снять попап + добрать CDR (пишется чуть позже hangup) → пайплайн
        if client:
            await self._dismiss_call_card(connector, env, client)
        uniqueid = adapter.message_id
        if uniqueid:
            await asyncio.sleep(0.5)
            cdrs = await self._fetch_calls_by_id(connector, uniqueid)
            await env.models.asterisk_log.record(
                connector.id,
                "cdr_read",
                event_type="fetch_calls_by_id",
                uniqueid=uniqueid,
                note=f"CDR по uniqueid={uniqueid}: строк {len(cdrs)}",
                payload={"uniqueid": uniqueid, "count": len(cdrs)},
            )
            for cdr in cdrs:
                await super().handle_webhook(connector, cdr, env)
        return {"ok": True}

    # ==================== живой попап (по ARI) ====================

    async def _connector_manager_ids(
        self, connector: "ChatConnector", env: "Environment"
    ) -> list[int]:
        session = env.apps.db.get_session()
        rows = await session.execute(
            "SELECT user_id FROM chat_connector_manager_many2many "
            "WHERE connector_id = %s",
            [connector.id],
        )
        return [row["user_id"] for row in (rows or [])]

    async def _send_call_card(
        self,
        connector: "ChatConnector",
        env: "Environment",
        client_number: str,
    ) -> None:
        """
        Карточка входящего звонка операторам (менеджерам коннектора).
        Клиента резолвим best-effort (имя партнёра + последний лид), сообщение
        НЕ создаём — оно придёт из CDR по завершению.
        """
        number = AsteriskPhoneAdapter.normalize_phone(client_number)

        name = number
        partner_id = None
        lead_id = None
        try:
            if connector.contact_type_id:
                contact = await env.models.contact.find_for_webhook(
                    contact_type=connector.contact_type_id, value=number
                )
                if contact and contact.partner_id:
                    partner_id = contact.partner_id.id
                    name = contact.partner_id.name or number
                    leads = await env.models.lead.search(
                        filter=[
                            ("partner_id", "=", partner_id),
                            ("connector_id", "=", connector.id),
                        ],
                        fields=["id"],
                        limit=1,
                        sort="id",
                        order="desc",
                    )
                    if leads:
                        lead_id = leads[0].id
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[phone_asterisk] call card resolve failed: %s", exc
            )

        card = {
            "type": "call.incoming",
            "call": {
                "number": number,
                "name": name,
                "direction": "incoming",
                "disposition": "answered",
                "partner_id": partner_id,
                "lead_id": lead_id,
                "connector_type": connector.type,
            },
        }
        for uid in await self._connector_manager_ids(connector, env):
            await env.apps.chat.chat_manager.send_to_user(uid, card)

    async def _dismiss_call_card(
        self,
        connector: "ChatConnector",
        env: "Environment",
        client_number: str,
    ) -> None:
        number = AsteriskPhoneAdapter.normalize_phone(client_number)
        msg = {"type": "call.ended", "call": {"number": number}}
        for uid in await self._connector_manager_ids(connector, env):
            await env.apps.chat.chat_manager.send_to_user(uid, msg)

    # ==================== запись через источник ====================

    async def _download_call_record(
        self, connector: "ChatConnector", adapter: AsteriskPhoneAdapter
    ) -> bytes | None:
        filename = adapter.recording_filename
        if not filename:
            return None
        content = await self._source(connector).download_recording(filename)
        if content and len(content) > 100:
            return content
        return None

    # ==================== история (pull через источник) ====================

    async def _fetch_calls_by_id(
        self, connector: "ChatConnector", uniqueid: str
    ) -> list[dict]:
        try:
            return await self._source(connector).fetch_calls_by_id(uniqueid)
        except Exception as e:  # noqa: BLE001
            logger.error("[phone_asterisk] fetch by id failed: %s", e)
            return []

    async def fetch_call_history(
        self,
        connector: "ChatConnector",
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        # Формат дат под источник выбирает САМ источник: local — наивный SQL-литерал
        # «YYYY-MM-DD HH:MM:SS»; remote — tz-aware ISO (агент валидирует AwareDatetime,
        # наивная дата → 422). Поэтому сюда передаём datetime-объекты, не строки.
        try:
            return await self._source(connector).fetch_call_history(
                start_date, end_date
            )
        except Exception as e:  # noqa: BLE001
            logger.error("[phone_asterisk] fetch history failed: %s", e)
            return []

    async def import_history(
        self,
        connector: "ChatConnector",
        start_date: datetime,
        end_date: datetime,
        env: "Environment",
        mode: str = "silent",
    ) -> dict:
        """
        Ручной импорт истории звонков из CDR за период (кнопка «Прочитать историю
        из CDR»). Тянет CDR через источник и прогоняет каждую запись через
        handle_webhook — пишет звонки в реестр call + записи. Дубли гасит дедуп
        по uniqueid, поэтому повторный импорт безопасен.

        start_date/end_date — timezone-aware (валидируются в ручке). В строку для
        CDR приводим по локальному времени сервера (как cron datetime.now()).

        mode — режим обработки исторических CDR (звонок уже состоялся, «как новый»
        его показывать/лидовать обычно не нужно):
        - normal    — как живой звонок (WS-попап + лид);
        - no_notify — без попапа, но с лидом;
        - silent    — без попапа и без лида (по умолчанию): только сообщение.
        """
        notify, generate_lead = CDR_IMPORT_MODES.get(mode, (False, False))
        # Даты передаём как datetime — формат под источник (SQL vs агент) выбирает
        # сам источник. Здесь строку делаем только для журнала.
        calls = await self.fetch_call_history(connector, start_date, end_date)
        period = (
            f"{start_date.astimezone():%Y-%m-%d %H:%M:%S}.."
            f"{end_date.astimezone():%Y-%m-%d %H:%M:%S}"
        )
        await env.models.asterisk_log.record(
            connector.id,
            "cdr_read",
            event_type="import_history",
            note=f"CDR {period} [{mode}]: строк {len(calls)}",
            payload={"period": period, "mode": mode, "count": len(calls)},
        )
        imported = 0
        for cdr in calls:
            try:
                await self.handle_webhook(
                    connector,
                    cdr,
                    env,
                    notify=notify,
                    generate_lead=generate_lead,
                )
                imported += 1
            except Exception as e:  # noqa: BLE001
                logger.error("[phone_asterisk] import history failed: %s", e)
        return {
            "ok": True,
            "imported": imported,
            "message": (
                f"Импортировано звонков: {imported} (из {len(calls)} CDR за "
                f"период, режим «{mode}»)"
            ),
        }

    # ==================== cron ====================

    @classmethod
    async def cron_fetch_call_history(cls, env: "Environment") -> dict:
        strategy = cls()
        connectors = await env.models.chat_connector.search(
            filter=[
                ("type", "=", "phone_asterisk"),
                ("active", "=", True),
            ],
            fields=[
                "id",
                "name",
                "agent_mode",
                "connector_url",
                "access_token",
                "refresh_token",
                "lead_generation",
                "lead_type",
                # local: колонки доступа к БД Asterisk (для fetch_call_history)
                "asterisk_db_dialect",
                "asterisk_db_host",
                "asterisk_db_port",
                "asterisk_db_database",
                "asterisk_db_user",
                "asterisk_db_password",
                "asterisk_db_table_cdr",
                # local: каталог записей (download_recording читает файл с диска)
                "asterisk_path_recordings",
            ],
        )
        total = 0
        for connector in connectors:
            end = datetime.now() - timedelta(minutes=cls.HISTORY_WAIT_MINUTES)
            start = end - timedelta(minutes=cls.HISTORY_WINDOW_MINUTES)
            # datetime вниз — формат под источник (SQL vs агент) там же.
            calls = await strategy.fetch_call_history(connector, start, end)
            period = f"{start:%Y-%m-%d %H:%M:%S}..{end:%Y-%m-%d %H:%M:%S}"
            await env.models.asterisk_log.record(
                connector.id,
                "cdr_read",
                event_type="fetch_call_history",
                note=f"CDR {period}: строк {len(calls)}",
                payload={"period": period, "count": len(calls)},
            )
            for cdr in calls:
                try:
                    # Крон — бэкфилл истории из CDR: без попапа и без лида (живой
                    # звонок ведёт ARI-поток отдельно, дубли гасит дедуп по call_id).
                    await strategy.handle_webhook(
                        connector, cdr, env, notify=False, generate_lead=False
                    )
                    total += 1
                except Exception as e:  # noqa: BLE001
                    logger.error("[phone_asterisk] cron process failed: %s", e)

        logger.info(
            "[phone_asterisk] cron imported %s calls from %s connectors",
            total,
            len(connectors),
        )
        return {"connectors": len(connectors), "calls": total}

    @classmethod
    async def cron_sync_numbers(cls, env: "Environment") -> dict:
        """
        Периодическая синхронизация номеров (то же, что кнопка «Синхронизировать
        номера», но для всех активных Asterisk-коннекторов). Аналог
        cron_fetch_call_history; в Odoo-модуле номера тоже обновляются по cron.
        """
        strategy = cls()
        connectors = await env.models.chat_connector.search(
            filter=[
                ("type", "=", "phone_asterisk"),
                ("active", "=", True),
            ],
            fields=[
                "id",
                "name",
                "agent_mode",
                # remote: REST-доступ к агенту
                "connector_url",
                "access_token",
                "refresh_token",
                # local: БД Asterisk (ring groups/queues) + ARI (endpoints)
                "asterisk_db_dialect",
                "asterisk_db_host",
                "asterisk_db_port",
                "asterisk_db_database",
                "asterisk_db_user",
                "asterisk_db_password",
                "asterisk_db_table_cdr",
                "asterisk_ari_url",
                "asterisk_ari_login",
                "asterisk_ari_password",
            ],
        )
        total = 0
        for connector in connectors:
            try:
                res = await strategy.sync_numbers(connector, env)
                total += (res.get("details") or {}).get("synced", 0)
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "[phone_asterisk] cron sync_numbers failed: %s", e
                )

        logger.info(
            "[phone_asterisk] cron synced numbers for %s connectors (%s lines)",
            len(connectors),
            total,
        )
        return {"connectors": len(connectors), "lines": total}
