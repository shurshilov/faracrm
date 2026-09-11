"""Saved filters application."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL


class SavedFiltersApp(App):
    """
    Модуль сохранённых фильтров
    """

    info = {
        "name": "Saved Filters",
        "summary": "Module for managing saved filters",
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
        "saved_filter": ACL.FULL,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env
        await self._init_saved_filter_rules(env)

    async def _init_saved_filter_rules(self, env: "Environment"):
        """
        Access rules для модели saved_filter.

        Цели:
          1. Пользователь видит фильтры, где он создатель, ИЛИ системные
             глобальные (user_id IS NULL — кладутся через post_init,
             например «Мои файлы» из attachments), ИЛИ ОБЩИЕ фильтры,
             которыми поделились коллеги (is_global == True). Правила на
             одну операцию объединяются через OR (см. Rule docstring),
             поэтому три read-правила дают объединение этих условий.
          2. Пользователь может обновлять и удалять ТОЛЬКО свои фильтры
             (свои = user_id == текущий). Это защищает общий фильтр
             коллеги: он виден всем (read), но менять/снимать общий статус
             и удалять может только автор. Системные глобальные (user_id
             IS NULL) не трогает никто из base_user.

        Важно: правила создаются идемпотентно (create-if-missing по имени),
        поэтому на уже развёрнутой базе новые read/update правила добавятся
        при следующем старте, не ломая существующие.
        """
        from backend.base.crm.security.models.rules import Rule

        model_id = await env.models.model.search_one(
            filter=[("name", "=", "saved_filter")],
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
                "name": "User can read own and global saved filters",
                "domain": [
                    ("user_id", "=", "{{user_id}}"),
                    "or",
                    ("user_id", "=", None),
                ],
                "perm_create": False,
                "perm_read": True,
                "perm_update": False,
                "perm_delete": False,
            },
            {
                # Общие фильтры коллег: видны всем (read-only для не-автора).
                # ORed с правилом выше → пользователь видит свои + системные
                # глобальные + расшаренные коллегами.
                "name": "User can read shared saved filters",
                "domain": [("is_global", "=", True)],
                "perm_create": False,
                "perm_read": True,
                "perm_update": False,
                "perm_delete": False,
            },
            {
                # Менять фильтр (в т.ч. снимать/ставить is_global, is_default)
                # может ТОЛЬКО автор. Без этого правила update был бы не
                # ограничен (ACL FULL, нет rule → пустой domain → все строки),
                # и коллега мог бы переписать чужой общий фильтр.
                "name": "User can update only own saved filters",
                "domain": [("user_id", "=", "{{user_id}}")],
                "perm_create": False,
                "perm_read": False,
                "perm_update": True,
                "perm_delete": False,
            },
            {
                "name": "User can delete only own saved filters",
                "domain": [("user_id", "=", "{{user_id}}")],
                "perm_create": False,
                "perm_read": False,
                "perm_update": False,
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
