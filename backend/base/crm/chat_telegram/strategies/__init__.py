# Copyright 2025 FARA CRM
# Chat module - telegram strategy

from .strategy import TelegramStrategy
from .adapter import TelegramMessageAdapter

__all__ = ["TelegramStrategy", "TelegramMessageAdapter"]
