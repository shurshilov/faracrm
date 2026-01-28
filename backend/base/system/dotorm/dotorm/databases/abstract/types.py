"""Database configuration types."""

from typing import Literal
from pydantic_settings import BaseSettings


class ContainerSettings(BaseSettings):
    reconnect_timeout: int = 10
    driver: Literal["asynch", "aiomysql", "asyncpg"]
    ssl: str = ""
    sync_db: bool = False


class PostgresPoolSettings(BaseSettings):
    host: str
    port: int
    user: str
    password: str
    database: str


class ClickhousePoolSettings(BaseSettings):
    host: str
    port: int
    user: str
    password: str
    database: str


# настройки драйвера для mysql отличаются
class MysqlPoolSettings(BaseSettings):
    host: str
    port: int
    user: str
    password: str
    db: str
