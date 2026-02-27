"""PostgreSQL database settings."""

from backend.base.system.dotorm.dotorm.databases.abstract.types import (
    ContainerSettings,
    PostgresPoolSettings,
)


class PostgresSettings(ContainerSettings, PostgresPoolSettings):
    """Combined PostgreSQL pool and container settings."""
