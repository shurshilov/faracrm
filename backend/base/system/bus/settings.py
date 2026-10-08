from typing import Literal

from pydantic_settings import BaseSettings


class BusSettings(BaseSettings):
    """Шина событий между процессами (.env: bus__backend, bus__redis_url)."""

    # "pg" — PostgreSQL LISTEN/NOTIFY (по умолчанию, без настройки),
    # "redis" — Redis Pub/Sub (нужен redis-сервер и pip install redis).
    backend: Literal["pg", "redis"] = "pg"
    redis_url: str = "redis://localhost:6379/0"
