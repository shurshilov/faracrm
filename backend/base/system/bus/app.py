"""
Шина событий между процессами — HTTP-воркерами и кроном: pub/sub поверх
PostgreSQL LISTEN/NOTIFY или Redis (bus__backend в .env).

Модули друг о друге не знают: каждый подписывается на свои типы событий
в своём startup и публикует через env.apps.bus. Событие получают все
процессы, включая отправителя.

    env.apps.bus.subscribe("studio_changed", handler)  # async handler(event)
    await env.apps.bus.publish("studio_changed", {"id": 1})
"""

import logging
from typing import TYPE_CHECKING, Awaitable, Callable

from backend.base.system.core.service import Service

from .pubsub import PubSubBackend, create_pubsub_backend

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)


class BusService(Service):
    """Межпроцессная шина событий."""

    info = {
        "name": "Bus",
        "summary": "Cross-process event bus: PostgreSQL LISTEN/NOTIFY or Redis",
        "author": "FARA ERP",
        "category": "System",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": [],
        "service": True,
        "service_start_before": True,
        # После базы (2): pg-бэкенду нужен её пул.
        "sequence": 3,
    }

    # Обработчики по типу события. Сервис — синглтон, словарь один;
    # подписываться можно и до старта шины.
    _handlers: dict[str, Callable[[dict], Awaitable[None]]] = {}
    _backend: PubSubBackend | None = None

    def subscribe(
        self, event_type: str, handler: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Получать события этого типа из всех процессов, включая свой."""
        self._handlers[event_type] = handler

    def unsubscribe(self, event_type: str) -> None:
        self._handlers.pop(event_type, None)

    @property
    def ready(self) -> bool:
        """Шина поднялась — события уходят в другие процессы."""
        return self._backend is not None

    async def publish(self, event_type: str, data: dict) -> bool:
        """Отправить событие всем процессам. Внутри транзакции pg-бэкенд
        шлёт его на COMMIT. False — шина не поднялась, событие осталось
        непосланным (вызывающий решает, обработать ли его на месте)."""
        if self._backend is None:
            return False
        await self._backend.publish(event_type, data)
        return True

    async def startup(self, app: "FastAPI") -> None:
        env: "Environment" = app.state.env
        settings = env.settings.bus
        backend = create_pubsub_backend(settings.backend)
        if settings.backend == "redis":
            await backend.setup(redis_url=settings.redis_url)
        else:
            pool = env.apps.db.get_pool()
            if not pool:
                logger.error(
                    "Bus: no asyncpg pool — events stay in this process"
                )
                return
            await backend.setup(pool=pool)
        await backend.start_listening(self._dispatch)
        self._backend = backend
        logger.info("Bus: started (backend=%s)", settings.backend)

    async def shutdown(self, app: "FastAPI") -> None:
        if self._backend is not None:
            await self._backend.stop()
            self._backend = None
            logger.info("Bus: stopped")

    async def _dispatch(self, event: dict) -> None:
        """Событие из шины — обработчику его типа; без подписчика — мимо."""
        handler = self._handlers.get(event.get("type", ""))
        if handler is not None:
            await handler(event)
