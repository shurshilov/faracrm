# Copyright 2025 FARA CRM
# Bus - Pub/Sub factory
"""
Фабрика pub/sub backend для шины (BusService).

Использование:
    from backend.base.system.bus.pubsub import create_pubsub_backend

    backend = create_pubsub_backend("pg")

Настройки (.env):
    bus__backend=pg          # PostgreSQL (default)
    bus__backend=redis       # Redis
    bus__redis_url=redis://localhost:6379/0
"""

import logging


from .base import PubSubBackend
from .pg_backend import PgPubSubBackend  # noqa: F401 (re-export)

logger = logging.getLogger(__name__)

__all__ = [
    "PubSubBackend",
    "PgPubSubBackend",
    "create_pubsub_backend",
]


def create_pubsub_backend(backend_type: str) -> PubSubBackend:
    """
    Фабрика для создания pub/sub backend.

    Args:
        backend_type: "pg" или "redis" (BusSettings.backend)

    Returns:
        Инстанс PubSubBackend
    """
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
            f"Unknown bus__backend='{backend_type}'. "
            f"Supported: 'pg', 'redis'"
        )
