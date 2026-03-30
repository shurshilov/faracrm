# Copyright 2025 FARA CRM
# Chat Phone MegaFon module - application configuration

from backend.base.system.core.app import App


class ChatPhoneMegafonApp(App):
    """
    Интеграция с МегаФон ВАТС (Виртуальная АТС).

    Добавляет:
    - Тип коннектора 'phone_megafon'
    - Стратегию обработки webhook команд MegaFon VATS
    - API для получения звонков, записей и инициации исходящих

    MegaFon VATS API:
    - Base URL: https://{domain}/crmapi/v1/
    - Auth: X-API-KEY header
    - Webhooks: POST с полем 'cmd' (history/event/contact/rating)
    - Auth webhook: crm_token в теле запроса

    Webhook команды:
    - history: завершённый звонок с записью
    - event: real-time события (INCOMING, ACCEPTED, COMPLETED, CANCELLED, OUTGOING, TRANSFERRED)
    - contact: запрос имени контакта по номеру
    - rating: оценка качества звонка

    Настройка коннектора:
    - connector_url: https://{domain}/crmapi/v1 (из ЛК МегаФон ВАТС)
    - access_token: API ключ (X-API-KEY)
    - vpbx_api_key: CRM токен (для валидации webhook)
    """

    info = {
        "name": "Chat Phone MegaFon",
        "summary": "MegaFon VATS telephony integration",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat_phone"],
        "sequence": 117,
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_phone_megafon.strategies import (
            MegafonPhoneStrategy,
        )

        register_strategy(MegafonPhoneStrategy)
