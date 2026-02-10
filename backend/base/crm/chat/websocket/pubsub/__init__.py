# Copyright 2025 FARA CRM
# Chat module - Pub/Sub factory
"""
Фабрика для создания pub/sub backend.

Backend устанавливается в chat_manager через set_pubsub() при startup.

Использование:
    from backend.base.crm.chat.websocket.pubsub import create_pubsub_backend

    backend = create_pubsub_backend(settings)
    chat_manager.set_pubsub(backend)

Настройки (.env):
    PUBSUB__BACKEND=pg          # PostgreSQL (default)
    PUBSUB__BACKEND=redis       # Redis
    PUBSUB__REDIS_URL=redis://localhost:6379/0
"""

import logging

from .base import PubSubBackend
from .pg_backend import PgPubSubBackend
from .settings import PubSubSettings

logger = logging.getLogger(__name__)

__all__ = [
    "PubSubBackend",
    "PgPubSubBackend",
    "PubSubSettings",
    "create_pubsub_backend",
]


def create_pubsub_backend(
    settings: PubSubSettings | None = None,
) -> PubSubBackend:
    """
    Фабрика для создания pub/sub backend из настроек.

    Args:
        settings: PubSubSettings. Если None — создаёт из env.

    Returns:
        Инстанс PubSubBackend
    """
    if settings is None:
        settings = PubSubSettings()

    backend_type = settings.backend.lower()

    if backend_type == "redis":
        # Ленивый импорт — redis_backend.py не загружается
        # если backend != "redis", не нужен pip install redis
        from .redis_backend import RedisPubSubBackend

        logger.info("PubSub: creating Redis Pub/Sub backend")
        return RedisPubSubBackend()
    elif backend_type == "pg":
        logger.info("PubSub: creating PostgreSQL NOTIFY/LISTEN backend")
        return PgPubSubBackend()
    else:
        raise ValueError(
            f"Unknown PUBSUB__BACKEND='{backend_type}'. "
            f"Supported: 'pg', 'redis'"
        )
