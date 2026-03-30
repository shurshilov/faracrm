# Copyright 2025 FARA CRM
# Chat Phone module - strategies

from .strategy import PhoneStrategyBase
from .adapter import PhoneMessageAdapter

__all__ = ["PhoneStrategyBase", "PhoneMessageAdapter"]
