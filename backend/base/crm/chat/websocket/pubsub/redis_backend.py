# Copyright 2025 FARA CRM
# Chat module - Redis Pub/Sub backend
"""
Redis Pub/Sub реализация PubSubBackend.

Архитектура:
  HTTP Worker 1:  SUBSCRIBE 'ws_events'  ←──┐
  HTTP Worker 2:  SUBSCRIBE 'ws_events'  ←──┤── Redis PUBLISH
  HTTP Worker N:  SUBSCRIBE 'ws_events'  ←──┤
  Cron Process:   PUBLISH(...)           ───┘

Преимущества перед PG NOTIFY:
  - Payload до 512 MB (vs 8 KB)
  - Throughput ~500K msg/s (vs ~10K)
  - Latency ~0.1 ms (vs ~0.5-2 ms)
  - Не расходует PG connection pool
  - Возможность channel-per-chat в будущем

Зависимости:
  pip install redis[hiredis]

Настройки (.env):
  PUBSUB__BACKEND=redis
  PUBSUB__REDIS_URL=redis://localhost:6379/0
"""

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from .base import PubSubBackend

logger = logging.getLogger(__name__)

REDIS_CHANNEL = "ws_events"


class RedisPubSubBackend(PubSubBackend):
    """Redis Pub/Sub backend."""

    def __init__(self) -> None:
        self._redis: Any = None
        self._pubsub: Any = None
        self._callback: Callable[[dict], Awaitable[None]] | None = None
        self._listener_task: asyncio.Task | None = None
        self._running: bool = False

    async def setup(self, **kwargs) -> None:
        """
        Инициализация Redis соединения.

        Args:
            **kwargs: redis_url — URL Redis сервера
                (default: "redis://localhost:6379/0").
        """
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise ImportError(
                "Redis pub/sub backend requires 'redis' package. "
                "Install with: pip install redis[hiredis]"
            ) from exc

        redis_url = kwargs.get("redis_url", "redis://localhost:6379/0")
        self._redis = aioredis.from_url(
            redis_url,
            decode_responses=True,
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )

        # Проверяем соединение
        try:
            await self._redis.ping()
            logger.info("RedisPubSubBackend: connected to %s", redis_url)
        except Exception:
            logger.error(
                "RedisPubSubBackend: connection failed", exc_info=True
            )
            raise

    async def start_listening(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Запустить подписку на Redis канал."""
        if self._running:
            logger.warning("RedisPubSubBackend: already listening")
            return

        self._callback = callback
        self._running = True

        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(REDIS_CHANNEL)

        # Запускаем фоновую задачу чтения сообщений
        self._listener_task = asyncio.create_task(
            self._listen_loop(), name="redis_pubsub_listener"
        )

        logger.info(
            "RedisPubSubBackend: listening on channel '%s'", REDIS_CHANNEL
        )

    async def _listen_loop(self) -> None:
        """
        Фоновый цикл чтения сообщений из Redis Pub/Sub.

        При разрыве соединения — автоматический reconnect.
        """
        while self._running:
            try:
                async for message in self._pubsub.listen():
                    if not self._running:
                        break

                    if message["type"] != "message":
                        continue

                    try:
                        data = json.loads(message["data"])
                    except (json.JSONDecodeError, TypeError):
                        logger.error(
                            "RedisPubSubBackend: invalid JSON: %s",
                            str(message["data"])[:100],
                        )
                        continue

                    if self._callback:
                        await self._safe_callback(data)

            except asyncio.CancelledError:
                break
            except Exception:
                if not self._running:
                    break
                logger.error(
                    "RedisPubSubBackend: listener error, "
                    "reconnecting in 1s...",
                    exc_info=True,
                )
                await asyncio.sleep(1)
                await self._reconnect()

    async def _reconnect(self) -> None:
        """Переподключение к Redis Pub/Sub."""
        try:
            if self._pubsub:
                await self._pubsub.close()
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(REDIS_CHANNEL)
            logger.info("RedisPubSubBackend: reconnected")
        except Exception:
            logger.error("RedisPubSubBackend: reconnect failed", exc_info=True)

    async def _safe_callback(self, data: dict) -> None:
        """Обёртка callback с обработкой ошибок."""
        try:
            await self._callback(data)
        except Exception:
            logger.error(
                "RedisPubSubBackend: error in callback", exc_info=True
            )

    async def publish(self, event_type: str, data: dict) -> None:
        """Опубликовать событие в Redis канал."""
        payload = json.dumps(
            {"type": event_type, **data},
            ensure_ascii=False,
            default=str,
        )

        try:
            await self._redis.publish(REDIS_CHANNEL, payload)
        except Exception:
            logger.error("RedisPubSubBackend: publish failed", exc_info=True)

    async def stop(self) -> None:
        """Остановить listener и закрыть соединение."""
        self._running = False

        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            try:
                await self._pubsub.unsubscribe(REDIS_CHANNEL)
                await self._pubsub.close()
            except (OSError, RuntimeError):
                pass

        if self._redis:
            try:
                await self._redis.close()
            except (OSError, RuntimeError):
                pass

        logger.info("RedisPubSubBackend: stopped")

    def is_healthy(self) -> bool:
        """Проверить что Redis listener работает."""
        return (
            self._running
            and self._redis is not None
            and self._listener_task is not None
            and not self._listener_task.done()
        )
