from fastapi import FastAPI

from backend.base.system.core.app import App
from backend.base.system.core.enviroment import Environment


class AdministrationApp(App):
    """
    Приложение добавляет ручки общей информации.
    """

    info = {
        "name": "App administration",
        "summary": "administration",
        "author": "Artem Shurshilov",
        "category": "Base",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": [],
        "post_init": True,
    }

    async def post_init(self, app: FastAPI):
        env: Environment = app.state.env
        # создаёт системную настройку `ui.demo_mode`,
        # которая управляет префиллом формы логина на фронте.
        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": "ui.demo_mode",
                    # По умолчанию True — удобно для первого запуска и демо-стендов.
                    # На проде переключить в False через UI system_settings.
                    "value": {"value": True},
                    "description": (
                        "Demo-режим интерфейса. Если True — форма логина "
                        "префилится admin/admin. Отключите на production."
                    ),
                    "module": "administration",
                    "is_system": True,
                    # Не меняется часто → кешируем до перезапуска.
                    # set_value() сам инвалидирует кеш при изменении.
                    "cache_ttl": -1,
                },
            ]
        )
        await super().post_init(app)
