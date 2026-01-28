from pydantic_settings import BaseSettings


class LoggerSettings(BaseSettings):
    log_level: str
