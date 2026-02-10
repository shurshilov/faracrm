# Copyright 2025 FARA CRM
# PubSub settings
"""
Настройки модуля pub/sub для WebSocket событий.

Переменные окружения:
    PUBSUB__BACKEND: str = "pg" - бэкенд ("pg" | "redis")
    PUBSUB__REDIS_URL: str = "redis://localhost:6379/0" - URL Redis
    PUBSUB__REDIS_CHANNEL: str = "ws_events" - канал Redis
    PUBSUB__PG_CHANNEL: str = "ws_events" - канал PostgreSQL NOTIFY

Пример .env:
    PUBSUB__BACKEND=pg
    # или для Redis:
    PUBSUB__BACKEND=redis
    PUBSUB__REDIS_URL=redis://localhost:6379/0
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class PubSubSettings(BaseSettings):
    """Настройки PubSub модуля."""

    model_config = SettingsConfigDict(
        env_prefix="PUBSUB__",
        extra="ignore",
    )

    # Бэкенд: "pg" или "redis"
    backend: Literal["pg", "redis"] = "pg"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"
    redis_channel: str = "ws_events"

    # ── PostgreSQL ──
    pg_channel: str = "ws_events"
    pg_max_payload: int = 7900
