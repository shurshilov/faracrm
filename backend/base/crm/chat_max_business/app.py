# Copyright 2025 FARA CRM
# Chat MAX (business) module - application

from backend.base.system.core.app import App


class ChatMaxBusinessApp(App):
    """Официальная бизнес-интеграция с MAX (platform-api.max.ru).

    В отличие от бот-коннектора (chat_max) и агрегатора (chat_max_wamm), это
    ОФИЦИАЛЬНЫЙ канал «MAX для бизнеса»: верифицированный бизнес-аккаунт может
    писать клиенту ПЕРВЫМ по номеру телефона (санкционировано платформой,
    без риска ограничений аккаунта).
    """

    info = {
        "name": "Chat MAX Business",
        "summary": (
            "Official MAX for Business API (platform-api.max.ru), "
            "write-first by phone"
        ),
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat"],
        "sequence": 122,
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_max_business.strategies import (
            MaxBusinessStrategy,
        )

        register_strategy(MaxBusinessStrategy)
