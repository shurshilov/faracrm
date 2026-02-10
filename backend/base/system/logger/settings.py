"""Logger settings."""

from pydantic_settings import BaseSettings


class LoggerSettings(BaseSettings):
    """Configuration for the logging module."""

    log_level: str
