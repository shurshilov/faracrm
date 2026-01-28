# Copyright 2025 FARA CRM
# Chat Avito module application

from backend.base.system.core.app import App


class ChatAvitoApp(App):
    """Приложение для интеграции с Avito."""

    info = {
        "name": "Chat Avito",
        "summary": "Avito integration for chat module",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat"],
        "sequence": 120,
    }

    def __init__(self):
        """Регистрация стратегии Avito."""
        super().__init__()

        from backend.base.crm.chat.strategies import register_strategy
        from .strategies import AvitoStrategy

        register_strategy.register(AvitoStrategy)
