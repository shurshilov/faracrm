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
  CHAT__PUBSUB_BACKEND=redis
  CHAT__REDIS_URL=redis://localhost:6379/0
"""

import asyncio
import json
import logging
from typing import Callable, Awaitable

from .base import PubSubBackend

logger = logging.getLogger(__name__)

REDIS_CHANNEL = "ws_events"


class RedisPubSubBackend(PubSubBackend):
    """Redis Pub/Sub backend."""

    def __init__(self):
        self._redis = None
        self._pubsub = None
        self._callback: Callable[[dict], Awaitable[None]] | None = None
        self._listener_task: asyncio.Task | None = None
        self._running = False

    async def setup(self, **kwargs) -> None:
        """
        Args:
            redis_url: Redis connection URL (default: redis://localhost:6379/0)
        """
        try:
            import redis.asyncio as aioredis
        except ImportError:
            raise ImportError(
                "Redis pub/sub backend requires 'redis' package. "
                "Install with: pip install redis[hiredis]"
            )

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
            logger.info(f"RedisPubSubBackend: connected to {redis_url}")
        except Exception as e:
            logger.error(f"RedisPubSubBackend: connection failed: {e}")
            raise

    async def start_listening(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
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
            f"RedisPubSubBackend: listening on channel '{REDIS_CHANNEL}'"
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
                            f"RedisPubSubBackend: invalid JSON: "
                            f"{str(message['data'])[:100]}"
                        )
                        continue

                    if self._callback:
                        try:
                            await self._callback(data)
                        except Exception as e:
                            logger.error(
                                f"RedisPubSubBackend: error in callback: {e}",
                                exc_info=True,
                            )

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._running:
                    break
                logger.error(
                    f"RedisPubSubBackend: listener error: {e}, "
                    f"reconnecting in 1s..."
                )
                await asyncio.sleep(1)

                # Reconnect
                try:
                    if self._pubsub:
                        await self._pubsub.close()
                    self._pubsub = self._redis.pubsub()
                    await self._pubsub.subscribe(REDIS_CHANNEL)
                    logger.info("RedisPubSubBackend: reconnected")
                except Exception as re:
                    logger.error(f"RedisPubSubBackend: reconnect failed: {re}")

    async def publish(self, event_type: str, data: dict) -> None:
        payload = json.dumps(
            {"type": event_type, **data},
            ensure_ascii=False,
            default=str,
        )

        try:
            await self._redis.publish(REDIS_CHANNEL, payload)
        except Exception as e:
            logger.error(
                f"RedisPubSubBackend: publish failed: {e}", exc_info=True
            )

    async def stop(self) -> None:
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
            except Exception:
                pass

        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass

        logger.info("RedisPubSubBackend: stopped")

    def is_healthy(self) -> bool:
        return (
            self._running
            and self._redis is not None
            and self._listener_task is not None
            and not self._listener_task.done()
        )
