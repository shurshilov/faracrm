# Copyright 2025 FARA CRM
# Chat Phone module - application configuration

from backend.base.system.core.app import App


class ChatPhoneApp(App):
    """
    Базовый модуль телефонии для чатов.

    Добавляет:
    - Базовую стратегию для телефонных коннекторов

    Конкретные провайдеры (Sipuni, Mango, etc.) реализуются
    в отдельных модулях, наследуя PhoneStrategyBase.
    """

    info = {
        "name": "Chat Phone",
        "summary": "Base telephony integration for chat module",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat"],
        "sequence": 115,
    }
