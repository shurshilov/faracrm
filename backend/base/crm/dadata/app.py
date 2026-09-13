# Copyright 2025 FARA CRM
# DaData module - application

from typing import TYPE_CHECKING

from backend.base.system.core.app import App

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment


class DadataApp(App):
    """Провайдер реквизитов DaData для модуля contract: по ИНН и по БИК."""

    info = {
        "name": "DaData",
        "summary": "Реквизиты контрагента по ИНН и банка по БИК через DaData",
        "author": "FARA CRM",
        "category": "Sales",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["contract"],
        "post_init": True,
        # Ставится сам: без ключа он ничего не делает, пока не нажали
        # «Заполнить» у поля, а тогда и подсказывает, где взять ключ.
        "auto_install": True,
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.contract.strategies import register_provider
        from backend.base.crm.dadata.strategies import DadataProvider

        register_provider(DadataProvider)

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        from backend.base.crm.dadata.strategies import SETTING_API_KEY

        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": SETTING_API_KEY,
                    "value": {"value": ""},
                    "description": (
                        "Ключ API DaData (dadata.ru → Мои ключи). Подсказки "
                        "бесплатны до 10 000 запросов в сутки"
                    ),
                    "module": "dadata",
                    "is_system": False,
                    "cache_ttl": 0,
                }
            ]
        )
