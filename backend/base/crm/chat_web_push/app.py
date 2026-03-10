# Copyright 2025 FARA CRM
from backend.base.system.core.app import App


class ChatWebPushApp(App):
    info = {
        "name": "Chat Web Push",
        "summary": "Web Push notifications for chat module",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat"],
        "sequence": 125,
    }

    def __init__(self):
        super().__init__()
        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_web_push.strategies import WebPushStrategy

        register_strategy(WebPushStrategy)
