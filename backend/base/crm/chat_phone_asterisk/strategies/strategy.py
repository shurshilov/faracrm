# Copyright 2025 FARA CRM
# Chat Phone Asterisk module - Asterisk / FreePBX strategy

import asyncio
import base64
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from backend.base.crm.chat_phone.strategies.strategy import PhoneStrategyBase
from .adapter import AsteriskPhoneAdapter

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.project_setup import ChatConnector

logger = logging.getLogger(__name__)


class AsteriskPhoneStrategy(PhoneStrategyBase):
    """
    Стратегия Asterisk / FreePBX.

    Транспорт — внешний Asterisk-agent (FastAPI рядом с АТС), как и у прочих
    провайдеров «событие приходит на webhook»:
    - ARI-события агент POST-ит на универсальный webhook FARA;
    - историю (CDR), записи разговоров и номера FARA тянет из REST API агента
      по HTTP Basic-auth (connector_url + access_token/refresh_token).

    CDR — источник истины по звонку: ARI-событие говорит ЧТО произошло, а данные
    (длительность, статус, запись) лежат в CDR. Поэтому на завершении звонка
    стратегия до-запрашивает CDR по uniqueid (final_call_records), а cron
    добирает историю за окно. Что делать с событием, решает IncomingCallPipeline.
    """

    strategy_type = "phone_asterisk"
    TIMEOUT = 30.0

    # ==================== REST внешнего Asterisk-agent ====================

    def _basic_auth_header(self, connector: "ChatConnector") -> dict:
        token = base64.b64encode(
            f"{connector.access_token or ''}:"
            f"{connector.refresh_token or ''}".encode()
        ).decode()
        return {"Authorization": f"Basic {token}"}

    async def _api_request(
        self,
        connector: "ChatConnector",
        path: str,
        params: dict | None = None,
        binary: bool = False,
    ):
        base_url = (connector.connector_url or "").rstrip("/")
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.get(
                f"{base_url}{path}",
                params=params,
                headers=self._basic_auth_header(connector),
            )
            if resp.status_code == 401:
                raise ValueError(f"Asterisk-agent auth error: {resp.text}")
            if resp.status_code == 404:
                return b"" if binary else []
            resp.raise_for_status()
            if binary:
                return resp.content
            return resp.json() if resp.text else []

    # ==================== абстрактные методы ====================

    async def get_or_generate_token(self, connector: "ChatConnector"):
        return None

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        # У агента нет API установки webhook — URL приёма ARI-событий указывается
        # в его конфиге вручную. Пингуем агент и напоминаем адрес.
        try:
            await self._api_request(connector, "/api/numbers/")
            logger.info(
                "Asterisk-agent доступен. Укажите в агенте URL ARI-событий: %s",
                connector.webhook_url,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Asterisk-agent проверка не удалась: %s", e)
        return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        return {"ok": True}

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> AsteriskPhoneAdapter:
        return AsteriskPhoneAdapter(connector, raw_message)

    # ==================== номера ====================

    async def fetch_numbers(self, connector: "ChatConnector") -> list[dict]:
        """
        Линии АТС: SIP-endpoints (kind='number'), ring groups (kind='group'),
        очереди (kind='queue'). Группы и очереди есть только во FreePBX — у
        raw-Asterisk агент отдаёт по ним 404 → пустой список.
        """
        endpoints = await self._api_request(connector, "/api/numbers/")
        groups = await self._api_request(
            connector, "/api/numbers/ring_groups/"
        )
        queues = await self._api_request(
            connector, "/api/numbers/queues_config/"
        )

        records: list[dict] = []
        for rec in endpoints or []:
            resource = rec.get("resource")
            if not resource:
                continue
            records.append(
                {
                    "external_id": resource,
                    "kind": "number",
                    "number": resource,
                    "extension": resource,
                    "name": resource,
                    "user_key": resource,
                    "raw": rec,
                }
            )

        for rec in groups or []:
            grpnum = rec.get("grpnum")
            if not grpnum:
                continue
            records.append(
                {
                    "external_id": f"group:{grpnum}",
                    "kind": "group",
                    "number": f"{grpnum}",
                    "extension": f"{grpnum}",
                    "name": f"{rec.get('description') or grpnum}/{grpnum}",
                    "user_key": None,
                    "raw": rec,
                }
            )

        for rec in queues or []:
            qext = rec.get("extension")
            if not qext:
                continue
            records.append(
                {
                    "external_id": f"queue:{qext}",
                    "kind": "queue",
                    "number": f"{qext}",
                    "extension": f"{qext}",
                    "name": f"{rec.get('descr') or qext}",
                    "user_key": None,
                    "raw": rec,
                }
            )

        return records

    # ==================== ARI-событие → CDR ====================

    async def final_call_records(
        self,
        connector: "ChatConnector",
        env: "Environment",
        adapter: AsteriskPhoneAdapter,
    ) -> list[dict] | None:
        """
        CDR-запись самодостаточна (None). ARI-хэнгап данных о звонке не несёт —
        до-запрашиваем CDR по uniqueid; он пишется чуть позже hangup, поэтому
        небольшая пауза. Дубли безопасны: звонок пишется upsert-ом по uniqueid.
        """
        if not adapter.is_ari or not adapter.message_id:
            return None

        await asyncio.sleep(0.5)
        cdrs = await self._fetch_calls_by_id(connector, adapter.message_id)
        await env.models.asterisk_log.record(
            connector.id,
            "cdr_read",
            event_type="fetch_calls_by_id",
            uniqueid=adapter.message_id,
            note=f"CDR по uniqueid={adapter.message_id}: строк {len(cdrs)}",
            payload={"uniqueid": adapter.message_id, "count": len(cdrs)},
        )
        return cdrs

    async def log_event(
        self,
        connector: "ChatConnector",
        env: "Environment",
        adapter: AsteriskPhoneAdapter,
    ) -> None:
        """ARI-события — в журнал телефонии (экран «События»)."""
        if not adapter.is_ari:
            return
        raw_type = adapter.raw.get("type")
        await env.models.asterisk_log.record(
            connector.id,
            "ari_event",
            event_type=raw_type,
            uniqueid=adapter.message_id,
            note=f"ARI {raw_type} → {adapter.event_type}",
            payload=adapter.raw,
        )

    # ==================== запись разговора ====================

    async def _download_call_record(
        self, connector: "ChatConnector", adapter: AsteriskPhoneAdapter
    ) -> bytes | None:
        filename = adapter.recording_filename
        if not filename:
            return None
        content = await self._api_request(
            connector,
            "/api/call/recording",
            params={"filename": filename},
            binary=True,
        )
        if content and len(content) > 100:
            return content
        return None

    # ==================== история (CDR через агент) ====================

    async def _fetch_calls_by_id(
        self, connector: "ChatConnector", uniqueid: str
    ) -> list[dict]:
        try:
            calls = await self._api_request(
                connector,
                "/api/calls/hisroty/uniqueid_or_linkedid",
                params={"uniqueid": uniqueid},
            )
            return calls if isinstance(calls, list) else []
        except Exception as e:  # noqa: BLE001
            logger.error("[phone_asterisk] fetch by id failed: %s", e)
            return []

    async def fetch_call_history(
        self,
        connector: "ChatConnector",
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        # Агент валидирует start/end как AwareDatetime (tz ОБЯЗАТЕЛЕН) — шлём ISO
        # с оффсетом; наивная дата → 422. astimezone(): aware→локальный, наивный→
        # локальный-aware. Для MySQL агент берёт wall-clock (оффсет игнорится),
        # так что локальное время сохраняется.
        try:
            calls = await self._api_request(
                connector,
                "/api/calls/hisroty/",
                params={
                    "start_date": start_date.astimezone().isoformat(),
                    "end_date": end_date.astimezone().isoformat(),
                },
            )
            return calls if isinstance(calls, list) else []
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
        """Импорт истории + строка в журнал телефонии (экран «События»)."""
        result = await super().import_history(
            connector, start_date, end_date, env, mode
        )
        period = (
            f"{start_date.astimezone():%Y-%m-%d %H:%M:%S}.."
            f"{end_date.astimezone():%Y-%m-%d %H:%M:%S}"
        )
        await env.models.asterisk_log.record(
            connector.id,
            "cdr_read",
            event_type="import_history",
            note=(
                f"CDR {period} [{mode}]: импортировано "
                f"{result['imported']} из {result['total']}"
            ),
            payload={"period": period, "mode": mode, **result},
        )
        return result
