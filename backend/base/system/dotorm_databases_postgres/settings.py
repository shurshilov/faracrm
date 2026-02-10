"""PostgreSQL database settings."""

from backend.base.system.dotorm.dotorm.databases.abstract.types import (
    ContainerSettings,
    PostgresPoolSettings,
)


class PostgresSettings(ContainerSettings, PostgresPoolSettings):
    """Combined PostgreSQL pool and container settings."""


# class Settings(BaseSettings):
#     model_config = SettingsConfigDict(extra="forbid")

#     "ПОддерживает работу с несколькими базами."
#     dotorm_databases_postgres: dict[str, PostgresSettings]
