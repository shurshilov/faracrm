# Copyright 2025 FARA CRM
# PostgreSQL NOTIFY/LISTEN pub/sub for cross-process WebSocket events
"""
Мост между процессами через PostgreSQL NOTIFY/LISTEN.

Проблема:
  WebSocket connections живут в памяти конкретного worker-а.
  При multi-worker или cron subprocess — нельзя отправить WS event
  из другого процесса.

Решение:
  Все WS events идут через pg_notify → PostgreSQL → все workers получают
  через LISTEN → каждый worker отправляет в свои локальные WS connections.

Архитектура:
  HTTP Worker 1:  LISTEN 'ws_events'  ←──┐
  HTTP Worker 2:  LISTEN 'ws_events'  ←──┤── PostgreSQL NOTIFY
  HTTP Worker N:  LISTEN 'ws_events'  ←──┤
  Cron Process:   pg_notify(...)      ───┘
  Any HTTP route: pg_notify(...)      ───┘

Использование:
  # Публикация (из любого процесса):
  await pg_pubsub.publish("send_to_chat", {
      "chat_id": 1,
      "message": {...},
      "exclude_user": 5,
  })

  # Подписка (в каждом HTTP worker при startup):
  await pg_pubsub.start_listening(on_event_callback)
"""

import asyncio
import json
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# Канал PostgreSQL для WS events
PG_CHANNEL = "ws_events"

# Максимальный размер payload pg_notify — 8000 bytes
PG_NOTIFY_MAX_PAYLOAD = 7900


class PgPubSub:
    """
    PostgreSQL NOTIFY/LISTEN pub/sub.

    publish() — отправляет event через pg_notify (из любого процесса).
    start_listening() — запускает фоновый LISTEN (в HTTP worker).
    """

    def __init__(self):
        self._listener_conn = None  # Выделенная connection для LISTEN
        self._listener_task: asyncio.Task | None = None
        self._pool = None  # asyncpg.Pool для publish
        self._callback: Callable[[dict], Awaitable[None]] | None = None
        self._running = False

    async def setup(self, pool) -> None:
        """
        Инициализация с asyncpg pool.
        Вызывается при startup HTTP worker-а.
        """
        self._pool = pool
        logger.info("PgPubSub: initialized with connection pool")

    async def start_listening(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """
        Запускает фоновую задачу LISTEN на канале ws_events.
        callback вызывается для каждого полученного event.

        ВАЖНО: использует отдельную connection (не из pool),
        т.к. LISTEN требует persistent connection.
        """
        if self._running:
            logger.warning("PgPubSub: already listening")
            return

        self._callback = callback
        self._running = True

        # Получаем отдельное соединение для LISTEN
        self._listener_conn = await self._pool.acquire()

        # Подписываемся на канал
        await self._listener_conn.add_listener(
            PG_CHANNEL, self._on_notification
        )

        logger.info(f"PgPubSub: listening on channel '{PG_CHANNEL}'")

    def _on_notification(
        self, connection, pid: int, channel: str, payload: str
    ) -> None:
        """
        Callback от asyncpg при получении NOTIFY.
        asyncpg вызывает это синхронно — создаём asyncio task.
        """
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error(
                f"PgPubSub: invalid JSON in notification: {payload[:100]}"
            )
            return

        if self._callback:
            asyncio.get_event_loop().create_task(self._safe_callback(data))

    async def _safe_callback(self, data: dict) -> None:
        """Обёртка для callback с обработкой ошибок."""
        try:
            await self._callback(data)
        except Exception as e:
            logger.error(f"PgPubSub: error in callback: {e}", exc_info=True)

    async def publish(self, event_type: str, data: dict) -> None:
        """
        Отправить event через pg_notify.
        Может вызываться из любого процесса (HTTP worker, cron, etc.).

        Args:
            event_type: Тип события (send_to_chat, send_to_user, etc.)
            data: Данные события
        """
        payload = json.dumps(
            {"type": event_type, **data},
            ensure_ascii=False,
            default=str,  # datetime → str
        )

        if len(payload.encode("utf-8")) > PG_NOTIFY_MAX_PAYLOAD:
            logger.error(
                f"PgPubSub: payload too large ({len(payload)} bytes), "
                f"event_type={event_type}"
            )
            return

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"SELECT pg_notify($1, $2)",
                PG_CHANNEL,
                payload,
            )

    async def stop(self) -> None:
        """Остановить LISTEN и освободить connection."""
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

        logger.info("PgPubSub: stopped listening")


# Глобальный singleton
pg_pubsub = PgPubSub()
