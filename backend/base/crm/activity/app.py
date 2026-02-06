from fastapi import FastAPI
from backend.base.system.core.app import App
from backend.base.system.core.enviroment import Environment
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.activity_type import ActivityType, INITIAL_ACTIVITY_TYPES


class ActivityApp(App):
    """
    Модуль активностей и уведомлений.

    - Activity: запланированные действия привязанные к записям
    - ActivityType: типы активностей (звонок, встреча, email, напоминание, задача)
    - ChatMessage @extend: res_model/res_id для привязки notification к записи
    - Системный чат: уведомления пользователя через существующий chat
    """

    info = {
        "name": "Activity",
        "summary": "Activities, reminders and notifications via system chat",
        "author": "FARA CRM",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "activity": ACL.FULL,
        "activity_type": ACL.FULL,
    }

    async def post_init(self, app: FastAPI):
        await super().post_init(app)
        env: Environment = app.state.env
        db_session = env.apps.db.get_session()

        # Начальные типы активностей
        for type_data in INITIAL_ACTIVITY_TYPES:
            existing = await env.models.activity_type.search(
                session=db_session,
                filter=[("name", "=", type_data["name"])],
            )
            if not existing:
                await env.models.activity_type.create(
                    session=db_session,
                    payload=ActivityType(**type_data),
                )

        # Крон-задача проверки дедлайнов
        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": "activity.check_interval_minutes",
                    "value": 60,
                    "description": "Интервал проверки дедлайнов активностей в минутах",
                    "module": "activity",
                    "is_system": False,
                },
            ]
        )
