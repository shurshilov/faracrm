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
        # Дефолт base_url берём из env (SettingsCore.base_url),
        # чтобы БД-запись при первом старте соответствовала тому,
        # что разработчик настроил в .env/docker-compose.
        base_url_default = getattr(
            env.settings, "base_url", "http://localhost:8090"
        )

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
                {
                    # Базовый URL сервера: используется для генерации
                    # webhook-URL и внешних ссылок. Дефолт берётся из env
                    # (BASE_URL), но админ может переопределить на лету
                    # через UI system_settings без рестарта.
                    "key": "core.base_url",
                    "value": {"value": base_url_default},
                    "description": (
                        "Базовый URL сервера. Используется для генерации "
                        "webhook-URL и внешних ссылок. По умолчанию "
                        "подхватывается из env-переменной BASE_URL."
                    ),
                    "module": "core",
                    "is_system": True,
                    # Редко меняется → кешируем до перезапуска.
                    "cache_ttl": -1,
                },
            ]
        )
        await super().post_init(app)
