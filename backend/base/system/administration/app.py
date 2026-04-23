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
        # Дефолты URL'ов берём из env (SettingsCore.site_url / .api_url),
        # чтобы записи в БД при первом старте соответствовали тому,
        # что разработчик настроил в .env/docker-compose.
        site_url_default = env.settings.site_url
        api_url_default = env.settings.api_url

        await env.models.system_settings.ensure_defaults(
            [
                {
                    # Demo-режим фронта: префил формы логина admin/admin.
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
                    # Корень сайта, где юзер открывает CRM в браузере.
                    # Используется для внешних ссылок в email, push-уведомлениях
                    # и для `javascript_origins` в OAuth-конфигах.
                    # На локалке: http://127.0.0.1:5173 (vite dev)
                    # На проде:   https://mydomain.com
                    "key": "core.site_url",
                    "value": {"value": site_url_default},
                    "description": (
                        "Корень сайта — URL, по которому пользователь "
                        "открывает CRM в браузере. Используется для внешних "
                        "ссылок и OAuth javascript_origins."
                    ),
                    "module": "core",
                    "is_system": True,
                    "cache_ttl": -1,
                },
                {
                    # URL бэкенда снаружи. Webhooks от Telegram/WhatsApp
                    # и OAuth redirect_uri (Google) работают через этот URL.
                    # На локалке: http://127.0.0.1:8090 (uvicorn напрямую)
                    # На проде:   https://mydomain.com/api (через nginx)
                    "key": "core.api_url",
                    "value": {"value": api_url_default},
                    "description": (
                        "URL бэкенда снаружи. Используется для webhook'ов "
                        "(Telegram/WhatsApp) и OAuth redirect_uri (Google)."
                    ),
                    "module": "core",
                    "is_system": True,
                    "cache_ttl": -1,
                },
            ]
        )
        await super().post_init(app)
