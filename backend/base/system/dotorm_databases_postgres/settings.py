from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.base.system.dotorm.dotorm.databases.abstract.types import (
    ContainerSettings,
    PostgresPoolSettings,
)


class PostgresSettings(ContainerSettings, PostgresPoolSettings): ...


# class Settings(BaseSettings):
#     model_config = SettingsConfigDict(extra="forbid")

#     "ПОддерживает работу с несколькими базами."
#     dotorm_databases_postgres: dict[str, PostgresSettings]
