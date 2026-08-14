# Copyright 2025 FARA CRM
# Chat Phone Asterisk - remote source (external Asterisk-agent REST)

import base64
import logging
from datetime import datetime

import httpx

from .base import AsteriskSourceBase

logger = logging.getLogger(__name__)


class RemoteAgentSource(AsteriskSourceBase):
    """
    Удалённый источник: внешний Asterisk-agent по HTTP (Basic-auth).

    Коннектор:
      * connector_url — базовый URL агента;
      * access_token  — login;
      * refresh_token — password.

    Входящие ARI-события приходят через универсальный webhook FARA (агент POST-ит
    их сам) — здесь только pull (история / записи / номера). Это сегодняшнее
    поведение chat_phone_asterisk, вынесенное из strategy.py без изменений логики.
    """

    TIMEOUT = 30.0

    def _basic_auth_header(self) -> dict:
        token = base64.b64encode(
            f"{self.connector.access_token or ''}:"
            f"{self.connector.refresh_token or ''}".encode()
        ).decode()
        return {"Authorization": f"Basic {token}"}

    async def _api_request(
        self, path: str, params: dict | None = None, binary: bool = False
    ):
        base_url = (self.connector.connector_url or "").rstrip("/")
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.get(
                f"{base_url}{path}",
                params=params,
                headers=self._basic_auth_header(),
            )
            if resp.status_code == 401:
                raise ValueError(f"Asterisk-agent auth error: {resp.text}")
            if resp.status_code == 404:
                return b"" if binary else []
            resp.raise_for_status()
            if binary:
                return resp.content
            return resp.json() if resp.text else []

    async def fetch_calls_by_id(self, uniqueid: str) -> list[dict]:
        calls = await self._api_request(
            "/api/calls/hisroty/uniqueid_or_linkedid",
            params={"uniqueid": uniqueid},
        )
        return calls if isinstance(calls, list) else []

    async def fetch_call_history(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        # Агент валидирует start/end как AwareDatetime (tz ОБЯЗАТЕЛЕН) — шлём ISO
        # с оффсетом; наивная дата → 422. astimezone(): aware→локальный, наивный→
        # локальный-aware. Для MySQL агент берёт wall-clock (оффсет игнорится),
        # так что локальное время сохраняется (как в рабочем модуле Odoo).
        calls = await self._api_request(
            "/api/calls/hisroty/",
            params={
                "start_date": start_date.astimezone().isoformat(),
                "end_date": end_date.astimezone().isoformat(),
            },
        )
        return calls if isinstance(calls, list) else []

    async def download_recording(self, filename: str) -> bytes | None:
        if not filename:
            return None

        content = await self._api_request(
            "/api/call/recording",
            params={"filename": filename},
            binary=True,
        )
        return content or None

    async def list_numbers(self):
        return await self._api_request("/api/numbers/")

    async def list_ring_groups(self):
        return await self._api_request("/api/numbers/ring_groups/")

    async def list_queues(self):
        return await self._api_request("/api/numbers/queues_config/")
