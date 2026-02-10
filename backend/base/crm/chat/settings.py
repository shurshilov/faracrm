# Copyright 2025 FARA CRM
# Chat module - settings
"""
Настройки модуля chat.

Переменные окружения:
    CHAT__PUBSUB_BACKEND: str = "pg"    - backend pub/sub: "pg" или "redis"
    CHAT__REDIS_URL: str = "redis://localhost:6379/0" - URL Redis (если backend=redis)

Примеры .env:
    # PostgreSQL (по умолчанию, zero config):
    CHAT__PUBSUB_BACKEND=pg

    # Redis:
    CHAT__PUBSUB_BACKEND=redis
    CHAT__REDIS_URL=redis://localhost:6379/0

    # Redis с паролем:
    CHAT__REDIS_URL=redis://:mypassword@redis-host:6379/0

    # Redis с SSL:
    CHAT__REDIS_URL=rediss://redis-host:6380/0
"""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatSettings(BaseSettings):
    """Настройки Chat модуля."""

    model_config = SettingsConfigDict(
        env_prefix="CHAT__",
        extra="ignore",
    )

    # Pub/Sub backend: "pg" (PostgreSQL LISTEN/NOTIFY) или "redis"
    pubsub_backend: Literal["pg", "redis"] = "pg"

    # Redis URL (используется только при pubsub_backend="redis")
    redis_url: str = "redis://localhost:6379/0"
