from typing import Literal

from pydantic_settings import BaseSettings


class AuthTokenSettings(BaseSettings):
    """Настройки Auth Token модуля."""

    cookie_secure: bool = False
    cookie_name: str = "session_cookie"
    cookie_samesite: Literal["lax", "strict", "none"] | None = "lax"
