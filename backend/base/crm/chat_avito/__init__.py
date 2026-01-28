# Copyright 2025 FARA CRM
# Chat Avito module

from .app import ChatAvitoApp
from .strategies import AvitoMessageAdapter, AvitoStrategy

__all__ = ["ChatAvitoApp", "AvitoStrategy", "AvitoMessageAdapter"]
