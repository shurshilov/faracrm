# Copyright 2025 FARA CRM
# Chat Phone module - application configuration

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL


class ChatPhoneApp(App):
    """
    Базовый модуль телефонии для чатов.

    Добавляет:
    - Базовую стратегию для телефонных коннекторов

    Конкретные провайдеры (Sipuni, Mango, etc.) реализуются
    в отдельных модулях, наследуя PhoneStrategyBase.
    """

    info = {
        "ui_menu": True,
        "ui_menu_name": "telephony",
        "name": "Chat Phone",
        "summary": "Base telephony integration for chat module",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat"],
        "sequence": 115,
        "post_init": True,
    }

    # phone_number справочник номеров телефонии: правит админ, юзерам чтение
    BASE_USER_ACL = {
        "phone_number": ACL.READ_ONLY,
        "call": ACL.READ_ONLY,
    }
    ROLE_ACL = {
        "system_admin": {
            "phone_number": ACL.FULL,
            "call": ACL.FULL,
        },
    }
