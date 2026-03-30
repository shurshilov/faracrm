# Copyright 2025 FARA CRM
# Chat Phone Sipuni module - application configuration

from backend.base.system.core.app import App


class ChatPhoneSipuniApp(App):
    """
    Интеграция с Sipuni (sipuni.com) для телефонии.

    Добавляет:
    - Тип коннектора 'phone_sipuni'
    - Стратегию обработки webhook событий Sipuni
    - API для получения звонков и записей

    Webhook события Sipuni:
    - event=1: начало внутреннего дозвона (is_inner_call=1)
    - event=2: завершение звонка (status=ANSWER|NOANSWER|BUSY|CANCEL...)
    - event=3: ответ на звонок (сняли трубку)

    Настройка:
    - login: логин Sipuni
    - password: пароль Sipuni
    - connector_url: https://sipuni.com/api
    """

    info = {
        "name": "Chat Phone Sipuni",
        "summary": "Sipuni telephony integration",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat_phone"],
        "sequence": 116,
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_phone_sipuni.strategies import (
            SipuniPhoneStrategy,
        )

        register_strategy(SipuniPhoneStrategy)
