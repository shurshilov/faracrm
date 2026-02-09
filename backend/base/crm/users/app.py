from fastapi import FastAPI
from backend.base.system.core.app import App
from backend.base.system.core.enviroment import Environment
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.users import User, ADMIN_USER_ID, SYSTEM_USER_ID


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

    async def post_init(self, app: FastAPI):
        await super().post_init(app)
        env: Environment = app.state.env

        await self._init_admin_user(env)
        await self._init_system_user(env)
        await self._init_user_rules(env)

    async def _init_admin_user(self, env: Environment):
        """Создаёт пользователя-администратора (id=1)."""
        user_admin = await env.models.user.search(
            filter=[("id", "=", ADMIN_USER_ID)], limit=1
        )
        if not user_admin:
            await env.models.user.create(
                payload=User(
                    name="Administrator",
                    login="admin",
                    # email="admin",
                    is_admin=True,
                    password_hash="8562bbd6efff81338d44778c206328c2f20897bb5ba3472c1b8c6ee68f8c452f12753b15d8ef92cf9bad00ac3fe56078db10d656947fe1b9f1cfd1bc148ac845",
                    password_salt="04da4b9d76a371ce0e7b518d85ed255ff86c663070832f7f669641705955332903f09cbc4481a3b07dc29dfa261d48140dcff6134d2cccb7f15c002068d602dd",
                ),
            )

    async def _init_system_user(self, env: Environment):
        """Создаёт системного пользователя (id=2) для автоматических операций."""
        user_system = await env.models.user.search(
            filter=[("id", "=", SYSTEM_USER_ID)], limit=1
        )
        if not user_system:
            await env.models.user.create(
                payload=User(
                    name="System",
                    login="system",
                    # email="system",
                    is_admin=True,
                    password_hash="",
                    password_salt="",
                ),
            )

    async def _init_user_rules(self, env: Environment):
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

        # Правило 1: Запрет удаления admin и system пользователей
        # Domain: id NOT IN (1, 2) - можно удалять только если id не 1 и не 2
        rule_name = "Protect admin and system users from deletion"
        existing = await env.models.rule.search(
            filter=[("name", "=", rule_name)],
            limit=1,
        )
        if not existing:
            await env.models.rule.create(
                payload=Rule(
                    name=rule_name,
                    active=True,
                    model_id=user_model_id,
                    role_id=None,  # Для всех ролей
                    domain=[["id", "not in", [1, 2]]],
                    perm_create=False,
                    perm_read=False,
                    perm_update=False,
                    perm_delete=True,  # Применяется только к delete
                ),
            )

        # Правило 2: Пользователь может редактировать только себя
        rule_name_2 = "User can only edit own profile"
        existing_2 = await env.models.rule.search(
            filter=[("name", "=", rule_name_2)],
            limit=1,
        )
        if not existing_2:
            await env.models.rule.create(
                payload=Rule(
                    name=rule_name_2,
                    active=True,
                    model_id=user_model_id,
                    role_id=None,  # Для всех ролей
                    domain=[["id", "=", "{{user_id}}"]],
                    perm_create=False,
                    perm_read=False,
                    perm_update=True,  # Применяется к update
                    perm_delete=True,  # И к delete (себя можно удалить)
                ),
            )
