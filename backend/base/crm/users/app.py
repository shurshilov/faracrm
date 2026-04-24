from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.users import User, ADMIN_USER_ID, SYSTEM_USER_ID, TEMPLATE_USER_ID


class UserApp(App):
    """
    Приложение которое добавляет пользователей
    """

    info = {
        "name": "Users",
        "summary": "This module allow manage users",
        "author": "Artem Shurshilov",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security", "languages"],
    }

    BASE_USER_ACL = {
        "user": ACL.NO_CREATE,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        await self._init_admin_user(env)
        await self._init_system_user(env)
        await self._init_template_user(env)  # ← новый шаблон
        await self._init_user_rules(env)

    async def _init_admin_user(self, env: "Environment"):
        """Создаёт пользователя-администратора (id=1)."""
        user_admin = await env.models.user.search(
            filter=[("id", "=", ADMIN_USER_ID)], limit=1
        )
        if not user_admin:
            await env.models.user.create(
                payload=User(
                    name="Administrator",
                    login="admin",
                    is_admin=True,
                    password_hash="8562bbd6efff81338d44778c206328c2f20897bb5ba3472c1b8c6ee68f8c452f12753b15d8ef92cf9bad00ac3fe56078db10d656947fe1b9f1cfd1bc148ac845",
                    password_salt="04da4b9d76a371ce0e7b518d85ed255ff86c663070832f7f669641705955332903f09cbc4481a3b07dc29dfa261d48140dcff6134d2cccb7f15c002068d602dd",
                ),
            )

    async def _init_system_user(self, env: "Environment"):
        """Создаёт системного пользователя (id=2) для автоматических операций."""
        user_system = await env.models.user.search(
            filter=[("id", "=", SYSTEM_USER_ID)], limit=1
        )
        if not user_system:
            await env.models.user.create(
                payload=User(
                    name="System",
                    login="system",
                    is_admin=True,
                    password_hash="",
                    password_salt="",
                ),
            )

    async def _init_template_user(self, env: "Environment"):
        """
        Создаёт шаблонного пользователя (id=3, login='default_internal').
        Используется как прототип при создании
        """

        existing = await env.models.user.search(
            filter=[("id", "=", TEMPLATE_USER_ID)], limit=1
        )
        if existing:
            return

        # Назначаем роль base_user шаблону
        base_user_role = await env.models.role.search(
            filter=[("code", "=", "base_user")],
            fields=["id"],
            limit=1,
        )

        default_user = await env.models.user.search(
            filter=[("login", "=", "default_internal")],
            limit=1,
        )
        if default_user:
            return
        # Создаём неактивного шаблонного пользователя
        await env.models.user.create(
            payload=User(
                name="Шаблон: Внутренний пользователь",
                login="default_internal",
                is_admin=False,
                # Пустые хеши — пользователь не может войти в систему
                password_hash="",
                password_salt="",
                home_page="/",
                layout_theme="modern",
                notification_popup=True,
                notification_sound=True,
                role_ids={"selected": base_user_role},
            ),
        )

    async def _init_user_rules(self, env: "Environment"):
        """Создаёт правила безопасности для пользователей."""
        from backend.base.crm.security.models.rules import Rule

        # Получаем model_id для user
        user_model = await env.models.model.search(
            filter=[("name", "=", "user")],
            limit=1,
        )
        if not user_model:
            return
        user_model_id = user_model[0]

        system_admin_role = await env.models.role.search(
            filter=[("code", "=", "system_admin")],
            fields=["id"],
            limit=1,
        )
        system_admin_role_id = (
            system_admin_role[0] if system_admin_role else None
        )

        rules = [
            # Правило 1: Запрет удаления admin и system пользователей.
            {
                "name": "Protect admin and system users from deletion",
                "role_id": None,
                "domain": [
                    [
                        "id",
                        "not in",
                        [ADMIN_USER_ID, SYSTEM_USER_ID, TEMPLATE_USER_ID],
                    ]
                ],
                "perm_create": False,
                "perm_read": False,
                "perm_update": False,
                "perm_delete": True,
            },
            # Правило 2: Пользователь может видеть и редактировать только себя.
            # Без этого правила рядовой юзер видит/меняет ВСЕХ юзеров
            {
                "name": "User can only see and edit own profile",
                "role_id": None,
                "domain": [["id", "=", "{{user_id}}"]],
                "perm_create": False,
                "perm_read": True,
                "perm_update": True,
                "perm_delete": True,
            },
        ]

        # Правило 3: system_admin видит всех пользователей.
        if system_admin_role_id:
            rules.append(
                {
                    "name": "System admin can see and edit all users",
                    "role_id": system_admin_role_id,
                    "domain": [],
                    "perm_create": False,
                    "perm_read": True,
                    "perm_update": True,
                    "perm_delete": False,
                }
            )

        for rule_data in rules:
            existing = await env.models.rule.search(
                filter=[("name", "=", rule_data["name"])],
                limit=1,
            )
            if existing:
                continue
            await env.models.rule.create(
                payload=Rule(
                    name=rule_data["name"],
                    active=True,
                    model_id=user_model_id,
                    role_id=rule_data["role_id"],
                    domain=rule_data["domain"],
                    perm_create=rule_data["perm_create"],
                    perm_read=rule_data["perm_read"],
                    perm_update=rule_data["perm_update"],
                    perm_delete=rule_data["perm_delete"],
                ),
            )
