import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from backend.base.system.core.app import App
from backend.base.system.core.enviroment import Environment
from backend.base.system.dotorm.dotorm.access import (
    set_access_checker,
    AccessDenied,
)
from backend.base.crm.security.acl_post_init_mixin import ACL, ACLPerms
from .models.models import Model
from .models.apps import App as AppModel
from .models.roles import Role
from .access_control import SecurityAccessChecker

log = logging.getLogger(__name__)


class SecurityApp(App):
    """
    Сервис который добавляет роли и права доступа
    """

    info = {
        "name": "Security",
        "summary": "RBAC access and models store",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "sequence": 1,  # Выполняется первым - создаёт роли и модели
        "depends": [],
    }

    BASE_USER_ACL = {
        "session": ACLPerms(
            create=True, read=True, update=False, delete=False
        ),
        "model": ACL.READ_ONLY,
        "app": ACL.READ_ONLY,
        "role": ACLPerms(create=True, read=True, update=True, delete=False),
        "access_list": ACL.NO_ACCESS,
        "rule": ACL.NO_ACCESS,
    }

    def handler_errors(self, app_server: FastAPI):
        """Регистрирует обработчики ошибок доступа."""

        async def access_denied_handler(request: Request, exc: AccessDenied):
            return JSONResponse(
                content={"error": "#ACCESS_DENIED", "message": exc.message},
                status_code=403,
            )

        app_server.add_exception_handler(AccessDenied, access_denied_handler)

    async def post_init(self, app: FastAPI):
        env: Environment = app.state.env

        # Регистрируем AccessChecker для DotORM
        set_access_checker(SecurityAccessChecker(env))

        # Регистрируем иконки приложений
        await self._init_app_icons(env)

        # ВАЖНО: Сначала создаём модели и роль base_user,
        # чтобы другие модули могли создать ACL
        await self._init_models(env)
        await self._init_apps(env)
        await self._init_base_role(env)
        await self._init_security_rules(env)

        # Системные настройки auth
        await self._init_system_settings(env)

        # Теперь вызываем родительский post_init, который создаст ACL
        await super().post_init(app)

    async def _init_system_settings(self, env: Environment):
        """Создаёт настройки по умолчанию для модуля auth."""
        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": "auth.session_ttl",
                    "value": {"value": 60 * 60 * 24},
                    "description": "Время жизни сессии в секундах (по умолчанию 24 часа)",
                    "module": "auth",
                    "is_system": True,
                    "cache_ttl": -1,
                },
            ]
        )

    async def _init_app_icons(self, env: Environment):
        """Сканирует модули и регистрирует иконки приложений."""
        from backend.base.crm.security.routers.app_icons import (
            register_app_icon,
        )
        import inspect

        registered = []

        # Берём коды из env.apps (атрибуты класса Apps)
        for app_code in env.apps.get_names():
            app_instance = getattr(env.apps, app_code, None)
            if not app_instance:
                continue

            # Получаем путь к модулю через inspect
            try:
                module = inspect.getmodule(app_instance.__class__)
                if module and hasattr(module, "__file__") and module.__file__:
                    # Путь к app.py -> папка модуля -> static/icon.svg
                    app_dir = os.path.dirname(module.__file__)
                    icon_path = os.path.join(app_dir, "static", "icon.svg")

                    if os.path.exists(icon_path):
                        abs_path = os.path.abspath(icon_path)
                        register_app_icon(app_code, abs_path)
                        registered.append(app_code)
            except Exception:
                continue

        if registered:
            log.info(f"Registered app icons: {', '.join(registered)}")

    async def _init_models(self, env: Environment):
        """Создаёт записи в таблице models для всех моделей."""
        models_names = env.models._get_models_names()
        if not models_names:
            return

        exist_models = await env.models.model.search(
            filter=[("name", "in", models_names)],
            fields=["id", "name"],
        )
        exist_names = {m.name for m in exist_models}

        for model_name in models_names:
            if model_name not in exist_names:
                await env.models.model.create(payload=Model(name=model_name))

    async def _init_apps(self, env: Environment):
        """Создаёт записи в таблице apps из env.apps."""
        app_codes = env.apps.get_names()

        if not app_codes:
            return

        exist_apps = await env.models.app.search(
            filter=[("code", "in", app_codes)],
            fields=["id", "code"],
        )
        exist_codes = {a.code for a in exist_apps}

        for code in app_codes:
            if code not in exist_codes:
                app_instance: App | None = getattr(env.apps, code, None)
                if app_instance and app_instance.info:
                    name = app_instance.info.get("name", code)
                else:
                    name = code

                await env.models.app.create(
                    payload=AppModel(code=code, name=name)
                )

    async def _init_base_role(self, env: Environment):
        """Создаёт базовую роль base_user."""
        security_app = await env.models.app.search(
            filter=[("code", "=", "security")],
            fields=["id"],
            limit=1,
        )
        if not security_app:
            raise ValueError("Not found security app")
        app_id = security_app[0].id

        existing_role = await env.models.role.search(
            filter=[("code", "=", "base_user")],
            fields=["id"],
            limit=1,
        )

        if not existing_role:
            await env.models.role.create(
                payload=Role(
                    code="base_user",
                    name="Internal User",
                    app_id=AppModel(id=app_id),
                )
            )

    async def _init_security_rules(self, env: "Environment"):
        """Создаёт правила безопасности для модуля безопасности."""
        from backend.base.crm.security.models.rules import Rule

        # Правило для chat: можно удалять только свои чаты (creator_id = user_id)
        session_model = await env.models.model.search(
            filter=[("name", "=", "session")],
            limit=1,
        )
        if session_model:
            rule_name = "User can read only own sessions"
            existing = await env.models.rule.search(
                filter=[("name", "=", rule_name)],
                limit=1,
            )
            if not existing:
                await env.models.rule.create(
                    payload=Rule(
                        name=rule_name,
                        active=True,
                        model_id=session_model[0],
                        role_id=None,
                        domain=[["user_id", "=", "{{user_id}}"]],
                        perm_create=False,
                        perm_read=True,
                        perm_update=False,
                        perm_delete=False,
                    ),
                )
