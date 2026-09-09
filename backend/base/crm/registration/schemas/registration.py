from pydantic import BaseModel, Field


class RegistrationStartInput(BaseModel, extra="forbid"):
    name: str = Field(min_length=1, max_length=256)
    # Логин = адрес в выбранном канале (для email — сам email).
    login: str = Field(min_length=3, max_length=256)
    password: str = Field(min_length=1, max_length=256)
    channel: str = Field(default="email", max_length=32)
    # Капча — только если установлен модуль captcha (иначе поля игнорируются).
    captcha_token: str | None = Field(default=None, max_length=64)
    captcha_answer: str | None = Field(default=None, max_length=16)


class RegistrationConfirmInput(BaseModel, extra="forbid"):
    login: str = Field(min_length=3, max_length=256)
    code: str = Field(min_length=1, max_length=16)
