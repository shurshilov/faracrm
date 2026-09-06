# Copyright 2025 FARA CRM
# Payment T-Bank module - application

from typing import TYPE_CHECKING

from backend.base.system.core.app import App

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment


class PaymentTinkoffApp(App):
    """Провайдер оплаты T-Bank (Тинькофф) для модуля payment."""

    info = {
        "name": "Payment T-Bank",
        "summary": "T-Bank (Tinkoff) acquiring with split payments",
        "author": "FARA CRM",
        "category": "Sales",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["payment"],
        "post_init": True,
        # Провайдер ставится вместе с маркетплейсом (он его depends), а не
        # сам по себе на первом старте — платежи по умолчанию выключены.
        "auto_install": False,
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.payment.strategies import register_provider
        from backend.base.crm.payment_tinkoff.strategies import (
            TinkoffProvider,
        )

        register_provider(TinkoffProvider)

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        from backend.base.crm.payment_tinkoff.strategies import (
            DEFAULT_API_URL,
            SETTING_API_URL,
            SETTING_PASSWORD,
            SETTING_TERMINAL_KEY,
        )

        common = {
            "module": "payment_tinkoff",
            "is_system": False,
            "cache_ttl": 0,
        }
        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": SETTING_TERMINAL_KEY,
                    "value": {"value": ""},
                    "description": "TerminalKey из личного кабинета T-Bank",
                    **common,
                },
                {
                    "key": SETTING_PASSWORD,
                    "value": {"value": ""},
                    "description": "Пароль терминала T-Bank (подпись запросов)",
                    **common,
                },
                {
                    "key": SETTING_API_URL,
                    "value": {"value": DEFAULT_API_URL},
                    "description": (
                        "Адрес API T-Bank. Тестовый контур — "
                        "https://rest-api-test.tinkoff.ru/v2/"
                    ),
                    **common,
                },
            ]
        )
