# Copyright 2025 FARA CRM
# Chat WhatsApp ChatApp module application

from backend.base.system.core.app import App


class ChatWhatsAppChatAppApp(App):
    """Приложение для интеграции с Whatsapp."""

    info = {
        "name": "Chat Whatsapp",
        "summary": "Whatsapp integration for chat module",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat"],
        "sequence": 120,
    }

    def __init__(self):
        """Регистрация стратегии Whatsapp."""
        super().__init__()
        from backend.base.crm.chat.strategies import register_strategy
        from .strategies import WhatsAppChatAppStrategy

        register_strategy.register(WhatsAppChatAppStrategy)
