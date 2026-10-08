from fastapi import FastAPI

from backend.base.system.core.app import App
from backend.base.system.core.enviroment import Environment


class AppsApp(App):
    """
    Реестр приложений в БД — таблица apps (models/apps.py): строка на
    каждое приложение из project_setup. По ней security группирует роли
    и собирает «Рабочие места», а apps_install хранит флаг установки.
    """

    info = {
        "name": "Apps",
        "summary": "Registry of apps from project_setup",
        "author": "FARA ERP",
        "category": "System",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": [],
        "post_init": True,
        # Раньше post_init остальных: security (1) создаёт роли по строкам
        # реестра, apps_install пишет флаг новым строкам.
        "sequence": 0,
        "core": True,
    }

    async def post_init(self, app: FastAPI):
        env: Environment = app.state.env
        await env.models.app.seed(env.apps)
        await super().post_init(app)
