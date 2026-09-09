# Copyright 2025 FARA CRM
# Chat module - abstract pub/sub backend (Strategy pattern)
"""
Абстрактный интерфейс для pub/sub backend.

Паттерн Strategy: конкретная реализация (PostgreSQL / Redis)
подставляется при startup на основе настроек.

Использование (в коде приложения):
    chat_manager.set_pubsub(backend)
    await chat_manager._pubsub.publish("send_to_users", {...})

Выбор backend — через env переменную PUBSUB__BACKEND:
    PUBSUB__BACKEND=pg       # PostgreSQL LISTEN/NOTIFY (default)
    PUBSUB__BACKEND=redis    # Redis Pub/Sub
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class PubSubBackend(ABC):
    """
    Абстрактный pub/sub backend.

    Контракт:
    - setup()           → инициализация соединения
    - start_listening() → запуск фонового listener с callback
    - publish()         → отправка события (из любого процесса)
    - stop()            → корректное завершение
    - is_healthy()      → проверка работоспособности

    Приём событий у всех бэкендов одинаковый — _dispatch(): каждое событие
    обрабатывается своей задачей, чтобы один медленный сокет не задерживал
    остальные, а ошибка callback не роняла listener.
    """

    def __init__(self) -> None:
        self._callback: Callable[[dict], Awaitable[None]] | None = None
        # Event loop держит задачи слабыми ссылками — без своей коллекции
        # задача может исчезнуть посреди выполнения (см. asyncio.create_task).
        self._tasks: set[asyncio.Task] = set()

    @abstractmethod
    async def setup(self, **kwargs) -> None:
        """
        Инициализация backend-а.

        Kwargs зависят от реализации:
        - PG:    pool=asyncpg.Pool
        - Redis: redis_url="redis://localhost:6379"
        """

    @abstractmethod
    async def start_listening(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """
        Запустить фоновый listener.

        callback вызывается для каждого полученного события.
        Должен быть idempotent — может вызываться повторно при reconnect.
        """

    @abstractmethod
    async def publish(self, event_type: str, data: dict) -> None:
        """
        Опубликовать событие.

        Args:
            event_type: Тип события (send_to_users, notify_new_chat, etc.)
            data: Данные события (будут JSON-сериализованы)
        """

    @abstractmethod
    async def stop(self) -> None:
        """Остановить listener и освободить ресурсы."""

    @abstractmethod
    def is_healthy(self) -> bool:
        """Проверить что backend жив и работает."""

    def _dispatch(self, data: dict) -> None:
        """Передать принятое событие в callback отдельной задачей."""
        if self._callback is None:
            return
        task = asyncio.get_running_loop().create_task(
            self._safe_callback(data)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _safe_callback(self, data: dict) -> None:
        """Обёртка callback с обработкой ошибок."""
        assert self._callback is not None
        try:
            await self._callback(data)
        except Exception:
            logger.error(
                "%s: error in callback", type(self).__name__, exc_info=True
            )
