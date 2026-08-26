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
from typing import Any, Awaitable, Callable

from .base import PubSubBackend

logger = logging.getLogger(__name__)

PG_CHANNEL = "ws_events"
PG_NOTIFY_MAX_PAYLOAD = 7900  # ~8KB minus overhead

# Как часто проверять, живо ли LISTEN-соединение. 15 секунд — компромисс:
# столько максимум длится «слепота» воркера после обрыва.
_HEALTH_INTERVAL = 15


class PgPubSubBackend(PubSubBackend):
    """PostgreSQL NOTIFY/LISTEN pub/sub."""

    def __init__(self) -> None:
        self._listener_conn: Any = None
        self._pool: Any = None
        self._callback: Callable[[dict], Awaitable[None]] | None = None
        self._running: bool = False
        self._supervisor: Any = None

    async def setup(self, **kwargs) -> None:
        """
        Инициализация с asyncpg pool.

        Args:
            **kwargs: pool — asyncpg connection pool (обязательный).
        """
        self._pool = kwargs["pool"]
        logger.info("PgPubSubBackend: initialized with connection pool")

    async def start_listening(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Запустить LISTEN на канале PostgreSQL."""
        if self._running:
            logger.warning("PgPubSubBackend: already listening")
            return

        self._callback = callback
        self._running = True

        await self._subscribe()
        self._supervisor = asyncio.create_task(self._supervise())

        logger.info("PgPubSubBackend: listening on channel '%s'", PG_CHANNEL)

    async def _subscribe(self) -> bool:
        """Взять соединение из пула и повесить на него LISTEN."""
        try:
            conn = await self._pool.acquire()
            await conn.add_listener(PG_CHANNEL, self._on_notification)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "PgPubSubBackend: не удалось подписаться на '%s': %s",
                PG_CHANNEL,
                exc,
            )
            return False
        self._listener_conn = conn
        return True

    async def _supervise(self) -> None:
        """
        Пересоздавать LISTEN, если соединение умерло.

        asyncpg сам подписку не восстанавливает: соединение, закрытое
        рестартом postgres или сетевым таймаутом, просто перестаёт приносить
        события. Публикация при этом продолжает работать — publish берёт из
        пула НОВОЕ соединение на каждую отправку. Поэтому воркер выглядит
        живым, но перестаёт ПОЛУЧАТЬ: его пользователей видят все, а он не
        видит никого и не получает сообщений чужих чатов. Молча и до
        перезапуска — поэтому проверяем сами.
        """
        while self._running:
            await asyncio.sleep(_HEALTH_INTERVAL)

            conn = self._listener_conn
            if conn is not None and not conn.is_closed():
                continue

            logger.warning(
                "PgPubSubBackend: LISTEN на '%s' потерян — переподписываюсь",
                PG_CHANNEL,
            )
            if conn is not None:
                self._listener_conn = None
                try:
                    await self._pool.release(conn)
                except Exception:  # noqa: BLE001
                    pass  # мёртвое соединение пул выбросит сам

            if await self._subscribe():
                logger.info("PgPubSubBackend: LISTEN восстановлен")

    def _on_notification(
        self,
        _connection: Any,
        _pid: int,
        _channel: str,
        payload: str,
    ) -> None:
        """Callback от asyncpg — синхронный, создаём asyncio task."""
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("PgPubSubBackend: invalid JSON: %s", payload[:100])
            return

        if self._callback:
            asyncio.get_event_loop().create_task(self._safe_callback(data))

    async def _safe_callback(self, data: dict) -> None:
        """Обёртка callback с обработкой ошибок."""
        try:
            await self._callback(data)
        except Exception:
            logger.error("PgPubSubBackend: error in callback", exc_info=True)

    async def publish(self, event_type: str, data: dict) -> None:
        """Отправить событие через pg_notify."""
        payload = json.dumps(
            {"type": event_type, **data},
            ensure_ascii=False,
            default=str,
        )

        payload_size = len(payload.encode("utf-8"))
        if payload_size > PG_NOTIFY_MAX_PAYLOAD:
            logger.error(
                "PgPubSubBackend: payload too large (%d bytes), "
                "event_type=%s",
                payload_size,
                event_type,
            )
            return

        async with self._pool.acquire() as conn:
            await conn.execute(
                "SELECT pg_notify($1, $2)",
                PG_CHANNEL,
                payload,
            )

    async def stop(self) -> None:
        """Остановить LISTEN и освободить соединение."""
        self._running = False

        if self._supervisor:
            self._supervisor.cancel()
            try:
                await self._supervisor
            except asyncio.CancelledError:
                pass
            self._supervisor = None

        if self._listener_conn:
            try:
                await self._listener_conn.remove_listener(
                    PG_CHANNEL, self._on_notification
                )
            except (OSError, RuntimeError):
                pass

            try:
                await self._pool.release(self._listener_conn)
            except (OSError, RuntimeError):
                pass

            self._listener_conn = None

        logger.info("PgPubSubBackend: stopped")

    def is_healthy(self) -> bool:
        """Проверить что LISTEN соединение активно."""
        conn = self._listener_conn
        # is_closed() обязателен: закрытое соединение остаётся объектом, и без
        # этой проверки метод рапортовал бы «здоров» у оглохшего воркера.
        return bool(
            self._running and conn is not None and not conn.is_closed()
        )
