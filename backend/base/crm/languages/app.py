from fastapi import FastAPI
from backend.base.system.core.app import App
from backend.base.system.core.enviroment import Environment
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.language import Language, INITIAL_LANGUAGES


class LanguageApp(App):
    """
    Модуль управления языками системы
    """

    info = {
        "name": "Languages",
        "summary": "This module allows manage system languages",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "language": ACL.READ_ONLY,
    }

    async def post_init(self, app: FastAPI):
        await super().post_init(app)
        env: Environment = app.state.env

        # Создание начальных языков
        db_session = env.apps.db.get_session()
        for lang_data in INITIAL_LANGUAGES:
            existing_langs = await env.models.language.search(
                session=db_session, filter=[("code", "=", lang_data["code"])]
            )
            if not existing_langs:
                await env.models.language.create(
                    session=db_session,
                    payload=Language(**lang_data),
                )
