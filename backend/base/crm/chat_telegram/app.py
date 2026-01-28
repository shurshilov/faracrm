# Copyright 2025 FARA CRM
# Chat Telegram module - application

from backend.base.system.core.app import App


class ChatTelegramApp(App):
    """Приложение для интеграции с Telegram."""

    info = {
        "name": "Chat Telegram",
        "summary": "Telegram integration for chat module",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat"],
        "sequence": 120,
    }

    def __init__(self):
        super().__init__()

        # Регистрируем стратегию
        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_telegram.strategies import TelegramStrategy

        register_strategy(TelegramStrategy)
