# Copyright 2025 FARA CRM
# Registration Email module - application

from typing import TYPE_CHECKING

from backend.base.system.core.app import App

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment


class RegistrationEmailApp(App):
    """Канал регистрации «email»: код подтверждения письмом."""

    info = {
        "name": "Registration Email",
        "summary": "Registration confirmation code by email",
        "author": "FARA CRM",
        "category": "Base",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["registration", "chat_email"],
        "post_init": True,
        # Канал ставится вместе с маркетплейсом (он его depends), а не сам
        # по себе на первом старте — регистрация по умолчанию выключена.
        "auto_install": False,
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.registration.strategies import register_channel
        from backend.base.crm.registration_email.strategies import (
            EmailRegistrationChannel,
        )

        register_channel(EmailRegistrationChannel)

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        from backend.base.crm.registration_email.strategies import (
            CONNECTOR_SETTING,
        )

        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": CONNECTOR_SETTING,
                    "value": {"value": None},
                    "description": (
                        "ID email-коннектора для писем подтверждения "
                        "регистрации. Пусто — первый активный email-коннектор."
                    ),
                    "module": "registration_email",
                    "is_system": False,
                    "cache_ttl": 0,
                }
            ]
        )
