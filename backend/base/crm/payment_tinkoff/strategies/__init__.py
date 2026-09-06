# Copyright 2025 FARA CRM
# Payment T-Bank module - strategies

from .tinkoff import (
    DEFAULT_API_URL,
    SETTING_API_URL,
    SETTING_PASSWORD,
    SETTING_TERMINAL_KEY,
    TinkoffProvider,
    make_token,
)

__all__ = [
    "TinkoffProvider",
    "make_token",
    "DEFAULT_API_URL",
    "SETTING_API_URL",
    "SETTING_PASSWORD",
    "SETTING_TERMINAL_KEY",
]
