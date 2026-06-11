# Copyright 2025 FARA CRM
# Chat MAX (bot) module - application

from backend.base.system.core.app import App


class ChatMaxBotApp(App):
    """Приложение для интеграции с мессенджером MAX (МАКС)."""

    info = {
        "name": "Chat MAX Bot",
        "summary": "MAX (МАКС) messenger integration for chat module",
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
        from backend.base.crm.chat_max_bot.strategies import MaxBotStrategy

        register_strategy(MaxBotStrategy)
