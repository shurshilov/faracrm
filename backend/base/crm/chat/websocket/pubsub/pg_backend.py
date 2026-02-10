# Copyright 2025 FARA CRM
# Chat module - PostgreSQL LISTEN/NOTIFY pub/sub backend
"""
PostgreSQL NOTIFY/LISTEN реализация PubSubBackend.

Архитектура:
  HTTP Worker 1:  LISTEN 'ws_events'  ←──┐
  HTTP Worker 2:  LISTEN 'ws_events'  ←──┤── PostgreSQL NOTIFY
  HTTP Worker N:  LISTEN 'ws_events'  ←──┤
  Cron Process:   pg_notify(...)      ───┘

Ограничения:
  - Payload max 8 KB (PostgreSQL limit)
  - Fire-and-forget (нет гарантии доставки)
  - Каждый worker держит 1 выделенное соединение для LISTEN
"""

import asyncio
import json
import logging
from typing import Callable, Awaitable

from .base import PubSubBackend

logger = logging.getLogger(__name__)

PG_CHANNEL = "ws_events"
PG_NOTIFY_MAX_PAYLOAD = 7900  # ~8KB minus overhead


class PgPubSubBackend(PubSubBackend):
    """PostgreSQL NOTIFY/LISTEN pub/sub."""

    def __init__(self):
        self._listener_conn = None
        self._pool = None
        self._callback: Callable[[dict], Awaitable[None]] | None = None
        self._running = False

    async def setup(self, **kwargs) -> None:
        """
        Args:
            pool: asyncpg connection pool
        """
        self._pool = kwargs["pool"]
        logger.info("PgPubSubBackend: initialized with connection pool")

    async def start_listening(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        if self._running:
            logger.warning("PgPubSubBackend: already listening")
            return

        self._callback = callback
        self._running = True

        self._listener_conn = await self._pool.acquire()
        await self._listener_conn.add_listener(
            PG_CHANNEL, self._on_notification
        )

        logger.info(f"PgPubSubBackend: listening on channel '{PG_CHANNEL}'")

    def _on_notification(
        self, connection, pid: int, channel: str, payload: str
    ) -> None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error(f"PgPubSubBackend: invalid JSON: {payload[:100]}")
            return

        if self._callback:
            asyncio.get_event_loop().create_task(self._safe_callback(data))

    async def _safe_callback(self, data: dict) -> None:
        try:
            await self._callback(data)
        except Exception as e:
            logger.error(
                f"PgPubSubBackend: error in callback: {e}", exc_info=True
            )

    async def publish(self, event_type: str, data: dict) -> None:
        payload = json.dumps(
            {"type": event_type, **data},
            ensure_ascii=False,
            default=str,
        )

        if len(payload.encode("utf-8")) > PG_NOTIFY_MAX_PAYLOAD:
            logger.error(
                f"PgPubSubBackend: payload too large "
                f"({len(payload)} bytes), event_type={event_type}"
            )
            return

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"SELECT pg_notify($1, $2)",
                PG_CHANNEL,
                payload,
            )

    async def stop(self) -> None:
        self._running = False

        if self._listener_conn:
            try:
                await self._listener_conn.remove_listener(
                    PG_CHANNEL, self._on_notification
                )
            except Exception:
                pass

            try:
                await self._pool.release(self._listener_conn)
            except Exception:
                pass

            self._listener_conn = None

        logger.info("PgPubSubBackend: stopped")

    def is_healthy(self) -> bool:
        return self._running and self._listener_conn is not None
