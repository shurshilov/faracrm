"""View settings application."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL


class ViewSettingsApp(App):
    """
    Модуль пользовательских настроек представлений.

    Сейчас — настройки колонок списков (column_setting): какие столбцы
    показывать в справочниках и в каком порядке, отдельно для каждого
    пользователя.
    """

    info = {
        "name": "View Settings",
        "summary": "Per-user list/view settings (visible columns, order)",
        "author": "FARA ERP",
        "category": "System",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
        # Инфраструктура всех списков — удалить из интерфейса нельзя.
        "core": True,
    }

    BASE_USER_ACL = {
        "column_setting": ACL.FULL,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env
        await self._init_column_setting_rules(env)

    async def _init_column_setting_rules(self, env: "Environment"):
        """
        Access rules для модели column_setting.

        Цель: пользователь работает ТОЛЬКО со своими настройками колонок
        (user_id == текущий). Создание — по ACL FULL (user_id проставляется
        дефолтом из сессии), чтение/изменение/удаление — только своих строк.
        """
        from backend.base.crm.security.models.rules import Rule

        model_id = await env.models.model.search_one(
            filter=[("name", "=", "column_setting")],
        )
        if not model_id:
            return

        base_user_role_id = await env.models.role.search_one(
            filter=[("code", "=", "base_user")],
            fields=["id"],
        )
        if not base_user_role_id:
            return

        rules = [
            {
                "name": "User can read own column settings",
                "domain": [("user_id", "=", "{{user_id}}")],
                "perm_create": False,
                "perm_read": True,
                "perm_update": False,
                "perm_delete": False,
            },
            {
                "name": "User can modify own column settings",
                "domain": [("user_id", "=", "{{user_id}}")],
                "perm_create": False,
                "perm_read": False,
                "perm_update": True,
                "perm_delete": True,
            },
        ]

        for rule_data in rules:
            existing = await env.models.rule.search_one(
                filter=[("name", "=", rule_data["name"])],
            )
            if existing:
                continue
            await env.models.rule.create(
                payload=Rule(
                    name=rule_data["name"],
                    active=True,
                    model_id=model_id,
                    role_id=base_user_role_id,
                    domain=rule_data["domain"],
                    perm_create=rule_data["perm_create"],
                    perm_read=rule_data["perm_read"],
                    perm_update=rule_data["perm_update"],
                    perm_delete=rule_data["perm_delete"],
                ),
            )
