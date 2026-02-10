# Copyright 2025 FARA CRM
# Chat module - abstract pub/sub backend (Strategy pattern)
"""
Абстрактный интерфейс для pub/sub backend.

Паттерн Strategy: конкретная реализация (PostgreSQL / Redis)
подставляется при startup на основе настроек.

Использование (в коде приложения):
    chat_manager.set_pubsub(backend)
    await chat_manager._pubsub.publish("send_to_chat", {...})

Выбор backend — через env переменную PUBSUB__BACKEND:
    PUBSUB__BACKEND=pg       # PostgreSQL LISTEN/NOTIFY (default)
    PUBSUB__BACKEND=redis    # Redis Pub/Sub
"""

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
    """

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
            event_type: Тип события (send_to_chat, send_to_user, etc.)
            data: Данные события (будут JSON-сериализованы)
        """

    @abstractmethod
    async def stop(self) -> None:
        """Остановить listener и освободить ресурсы."""

    @abstractmethod
    def is_healthy(self) -> bool:
        """Проверить что backend жив и работает."""
