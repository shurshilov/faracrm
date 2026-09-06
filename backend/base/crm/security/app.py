import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from backend.base.crm.security.exceptions import AuthException
from backend.base.system.core.app import App
from backend.base.system.core.enviroment import Environment
from backend.base.system.core.service import Service
from backend.base.system.dotorm.dotorm.access import (
    set_access_checker,
)
from backend.base.crm.security.acl_post_init_mixin import ACL, ACLPerms
from .models.models import Model
from .models.apps import App as AppModel
from .models.roles import Role
from .models.workspace import Workspace
from .access_control import SecurityAccessChecker

log = logging.getLogger(__name__)


class SecurityApp(Service):
    """
    Сервис который добавляет роли и права доступа
    """

    info = {
        "ui_menu": True,
        "ui_menu_name": "settings",
        "name": "Security",
        "summary": "RBAC access and models store",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "sequence": 1,  # Выполняется первым - создаёт роли и модели
        "depends": [],
        "service": True,
    }

    BASE_USER_ACL = {
        "session": ACLPerms(
            create=True, read=True, update=False, delete=False
        ),
        "model": ACL.READ_ONLY,
        "app": ACL.READ_ONLY,
        "role": ACL.READ_ONLY,
        # Своё «Рабочее место» юзер может читать (для бейджа/справки), но не
        # менять — назначает админ (см. ROLE_ACL.system_admin ниже).
        "workspace": ACL.READ_ONLY,
        # "access_list": ACL.NO_ACCESS,
        # "rule": ACL.NO_ACCESS,
    }

    # ACL для роли system_admin — полный контроль системы прав.
    # В коде role создана в _init_base_role (код "system_admin").
    # Обычные юзеры этой роли НЕ получают по умолчанию — назначается админом.
    ROLE_ACL = {
        "system_admin": {
            "role": ACL.FULL,
            "access_list": ACL.FULL,
            "rule": ACL.FULL,
            # Управление «Рабочими местами» — часть настроек доступа.
            "workspace": ACL.FULL,
        },
    }

    def handler_errors(self, app_server: FastAPI):
        """Регистрирует обработчики ошибок доступа и аутентификации."""

        async def password_failed_handler(request: Request, exc: Exception):
            return JSONResponse(
                content={
                    "error": "#PASSWORD_FAILED",
                    "message": "Invalid password",
                },
                status_code=401,
            )

        async def user_not_exist_handler(request: Request, exc: Exception):
            return JSONResponse(
                content={
                    "error": "#USER_NOT_FOUND",
                    "message": "User not found",
                },
                status_code=401,
            )

        app_server.add_exception_handler(
            AuthException.PasswordFailed, password_failed_handler
        )
        app_server.add_exception_handler(
            AuthException.UserNotExist, user_not_exist_handler
        )

    async def startup(self, app) -> None:
        """Старт сервиса"""
        await super().startup(app)
        # Регистрируем глобальные обработчики ошибок
        self.handler_errors(app)

    async def post_init(self, app: FastAPI):
        env: Environment = app.state.env

        # Регистрируем AccessChecker для DotORM
        set_access_checker(SecurityAccessChecker(env))

        # Регистрируем иконки приложений
        await self._init_app_icons(env)

        # ВАЖНО: Сначала создаём модели и роль base_user,
        # чтобы другие модули могли создать ACL
        await self._init_models(env)
        # _init_apps переносит ui_menu/ui_menu_name из модулей на строки App.
        await self._init_apps(env)
        await self._init_base_role(env)
        # Дефолтные «Рабочие места» (из запроса App.ui_menu) + бэкфилл.
        await self._init_default_workspaces(env)
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
                    "value": {"value": 60 * 60 * 24 * 7},
                    "description": "Время жизни сессии в секундах (по умолчанию 7 дней)",
                    "module": "auth",
                    "is_system": True,
                    "cache_ttl": -1,
                },
                {
                    "key": "auth.password_policy",
                    "value": {
                        "preset": "basic",
                        "min_length": 5,
                        "require_uppercase": False,
                        "require_lowercase": False,
                        "require_digits": False,
                        "require_special": False,
                    },
                    "description": (
                        "Парольная политика. "
                        "preset: basic (только длина), medium (буквы + цифры), "
                        "strong (заглавные + строчные + цифры + спецсимволы), "
                        "custom (ручная настройка флагов)"
                    ),
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
            except Exception as e:
                log.warning("Application registration failed: %s", e)
                continue

        if registered:
            log.info("Registered app icons: %s", ", ".join(registered))

    async def _init_models(self, env: Environment):
        """Создаёт записи в таблице models для всех моделей.

        Помимо name сохраняем table (__table__ модели) — так по связи model_id
        сразу доступно имя таблицы (напр. в маршрутах вложений), без обратного
        маппинга env-имя -> таблица. Для уже существующих записей table
        бэкфиллится идемпотентно.
        """
        models_names = env.models._get_models_names()
        if not models_names:
            return

        exist_models = await env.models.model.search(
            filter=[("name", "in", models_names)],
            fields=["id", "name", "table_name"],
        )
        exist_by_name = {m.name: m for m in exist_models}

        for model_name in models_names:
            table = env.models._get_model(model_name).__table__
            existing = exist_by_name.get(model_name)
            if existing is None:
                await env.models.model.create(
                    payload=Model(name=model_name, table_name=table)
                )
            elif table and existing.table_name != table:
                # Бэкфилл имени таблицы у ранее созданных записей реестра
                await existing.update(env.models.model(table_name=table))

    async def _init_apps(self, env: Environment):
        """Создаёт/обновляет записи в таблице apps из env.apps.

        Каждый модуль может объявить у себя атрибуты ui_menu / ui_menu_name
        (см. модель App) — тогда его строка становится «UI-приложением»
        (плиткой лаунчера). Флаги переносятся сюда и для НОВЫХ, и для уже
        существующих строк (идемпотентно), чтобы после обновления кода
        объявления подхватывались без пересоздания apps.

        installed у новой строки — из env.installed (правило auto_install,
        см. Environment.load_installed); дальше его меняет только установка
        и удаление. Core установлено всегда.
        """
        app_codes = env.apps.get_names()

        if not app_codes:
            return

        exist_apps = await env.models.app.search(
            filter=[("code", "in", app_codes)],
            fields=["id", "code", "installed"],
        )
        exist_by_code = {a.code: a for a in exist_apps}

        for code in app_codes:
            app_instance: App | None = env.apps.get(code)
            info = (
                app_instance.info if app_instance and app_instance.info else {}
            )
            name = info.get("name", code)
            ui_menu = bool(info.get("ui_menu", False))
            ui_menu_name = info.get("ui_menu_name")

            existing = exist_by_code.get(code)
            if existing is None:
                await env.models.app.create(
                    payload=AppModel(
                        code=code,
                        name=name,
                        ui_menu=ui_menu,
                        ui_menu_name=ui_menu_name,
                        installed=env.is_installed(code),
                    )
                )
                continue

            changed = {}
            # Обновляем ТОЛЬКО UI-флаги у объявленных приложений; имя и
            # прочее у существующих строк не трогаем.
            if ui_menu or ui_menu_name:
                changed.update(ui_menu=ui_menu, ui_menu_name=ui_menu_name)
            if env.apps.is_core(code) and not existing.installed:
                changed["installed"] = True
            if changed:
                await existing.update(payload=AppModel(**changed))

    async def _init_default_workspaces(self, env: Environment):
        """Сидит два «Рабочих места» и раздаёт базовое.

        - «Сотрудник» = то, что видит Internal User (base_user): Общение,
          Партнёры, Активности, Файлы. Дефолт для новых юзеров и БЭКФИЛЛ
          существующих без РМ — иначе после включения фичи (нет РМ → ничего
          не видно) у них будет пустой лаунчер.
        - «Все приложения» = все UI-приложения (для power-юзеров).
        Идемпотентно по name; app_ids приводится к целевому набору на каждом
        старте (m2m пишется через update selected). Имя базового РМ берётся
        из users.DEFAULT_WORKSPACE_NAME (единый источник).
        """
        # Имя базового РМ — из ЕДИНОЙ константы (users.models.users), чтобы
        # совпадало с User._default_workspace (дефолт поля workspace_id).
        from backend.base.crm.users.models.users import (
            DEFAULT_WORKSPACE_NAME,
        )

        async def _ensure_workspace(
            name: str, app_ids: list[int], seq: int
        ) -> int:
            existing = await env.models.workspace.search(
                filter=[("name", "=", name)], fields=["id"], limit=1
            )
            if existing:
                ws_id = existing[0].id
            else:
                ws_id = await env.models.workspace.create(
                    payload=Workspace(name=name, active=True, sequence=seq)
                )
            ws = await env.models.workspace.get(ws_id)
            await ws.update(payload=Workspace(app_ids={"selected": app_ids}))
            return ws_id

        async def _app_ids_where(filter_: list) -> list[int]:
            rows = await env.models.app.search(filter=filter_, fields=["id"])
            return [r.id for r in rows]

        # Базовое РМ = то, что видит Internal User. Запрос среди UI-приложений
        # по ui_menu_name (это ключи групп меню на фронте).
        base_names = ["communication", "contacts", "activity", "files"]
        base_ids = await _app_ids_where(
            [("ui_menu_name", "in", base_names), ("ui_menu", "=", True)]
        )
        base_ws_id = await _ensure_workspace(
            DEFAULT_WORKSPACE_NAME, base_ids, 1
        )

        # «Все приложения» = ВСЕ UI-приложения ЗАПРОСОМ из БД (ui_menu=true).
        all_ids = await _app_ids_where([("ui_menu", "=", True)])
        await _ensure_workspace("Все приложения", all_ids, 2)

        # Бэкфилл: НЕ-админам без РМ → базовое (иначе пустой лаунчер). Админам
        # РМ НЕ назначаем — они видят всё через байпас (и бейджа быть не должно).
        users_wo_ws = await env.models.user.search(
            filter=[("workspace_id", "=", None), ("is_admin", "=", False)],
            fields=["id"],
        )
        for u in users_wo_ws:
            user = await env.models.user.get(u.id)
            await user.update(
                payload=env.models.user(
                    workspace_id=env.models.workspace(id=base_ws_id)
                )
            )

    async def _init_base_role(self, env: Environment):
        """Создаёт базовую роль base_user и системную роль system_admin."""
        security_app = await env.models.app.search(
            filter=[("code", "=", "security")],
            fields=["id"],
            limit=1,
        )
        if not security_app:
            raise ValueError("Not found security app")
        app_id = security_app[0].id

        # base_user — базовая роль для всех пользователей
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

        # system_admin — системная роль для доступа к настройкам.
        # Отличие от is_admin: is_admin обходит ВСЕ проверки (суперпользователь),
        # system_admin — обычная роль с доступом к модулю настроек через меню.
        existing_system = await env.models.role.search(
            filter=[("code", "=", "system_admin")],
            fields=["id"],
            limit=1,
        )

        if not existing_system:
            # system_admin наследует base_user
            base_user = await env.models.role.search(
                filter=[("code", "=", "base_user")],
                fields=["id"],
                limit=1,
            )

            new_role_id = await env.models.role.create(
                payload=Role(
                    code="system_admin",
                    name="Администратор настроек",
                    app_id=AppModel(id=app_id),
                )
            )
            # m2m (based_role_ids) сохраняются только через update(),
            # link_many2many ожидает int id (не объекты).
            if base_user:
                new_role = await env.models.role.get(new_role_id)
                await new_role.update(
                    payload=Role(
                        based_role_ids={"selected": [base_user[0].id]}
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
