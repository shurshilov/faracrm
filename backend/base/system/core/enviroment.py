import importlib
import os
import pkgutil
import platform
from typing import TYPE_CHECKING
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from backend.project_setup import Models, Settings, Apps

from .exceptions import environment
from .service import Service

# Advisory-лок сидеров post_init (см. start_post_init). Ключ отличается от
# DDL_LOCK_ID (dotorm/databases/postgres/pool.py): там сериализуется схема,
# здесь — данные.
POST_INIT_LOCK_ID = 0xFA4A5EED


class Environment:
    """
    Паттерн проектирования синглтон (порождающий шаблон)
    Обеспечение создания одного и только одного объекта класса.
    А также паттерн фасад.
    """

    spliter: str = "\\" if platform.system() == "Windows" else "/"

    def __add_router(self, app: FastAPI, router: APIRouter):
        """Приватный метод добавления роута"""

        if router:
            if isinstance(router, APIRouter):
                app.include_router(router)
            else:
                raise environment.RouterNoValid()

    def get_python_import(self, file_path: str):
        """Преобразовать путь файла в пайтон импорт
        с дот-нотацией.
        """

        return file_path.removesuffix(".py").replace(self.spliter, ".")[2:]

    # ── Установка / удаление приложений ──────────────────────────────
    #
    # Код всех модулей загружен всегда (модели, стратегии, таблицы), а вот
    # РОУТЫ есть только у установленных: установка монтирует роутеры модуля
    # прямо в работающий процесс, удаление их вырезает. У каждого воркера
    # свои роуты, поэтому «что установлено» решает БД (apps.installed), а
    # воркеры узнают об изменении по шине (apps_changed) и приводят свои
    # роуты в соответствие — sync_routers. Удаление — только флаг: данные и
    # роли остаются, повторная установка возвращает всё как было.

    def is_installed(self, code: str) -> bool:
        """Установлено ли приложение (по коду = имени в Apps)."""
        return code in self.installed

    async def load_installed(self) -> set[str]:
        """Перечитать из БД, какие приложения установлены.

        Core — всегда. Со строкой в apps — как в БД. Без строки (первый
        старт, новый модуль в коде) — auto_install из info, по умолчанию
        True. Сырой SQL: вызывается до регистрации AccessChecker и вне сессии.
        """
        db = self.models.app._get_db_session()
        try:
            rows = await db.execute(
                "SELECT code, installed FROM apps", [], cursor="fetch"
            )
        except Exception:
            rows = []  # таблицы ещё нет (sync_db выключен)
        known = {r["code"]: r["installed"] is not False for r in rows}
        self.installed = {
            code
            for code in self.apps.get_names()
            if self.apps.is_core(code)
            or known.get(
                code, self.apps.get(code).info.get("auto_install", True)
            )
        }
        return self.installed

    def sync_routers(self, app: FastAPI) -> None:
        """Привести роуты процесса к env.installed: смонтировать роутеры
        новых установленных, вырезать роутеры удалённых. Идемпотентно."""
        for code in self.apps.get_names():
            if code in self.installed and code not in self._routes:
                self._mount(app, code)
            elif code not in self.installed and code in self._routes:
                self._unmount(app, code)

    def _mount(self, app: FastAPI, code: str) -> None:
        """Подключить роутеры пакета приложения и запомнить, какие роуты
        его — по ним же они потом вырезаются."""
        app_module = self.apps.get(code).__class__.__module__
        # app_module например "backend.base.system.administration.app"
        package_import_path = app_module.rsplit(".", 1)[0] + ".routers"
        before = len(app.router.routes)
        self._include_routers_from_package(app, package_import_path)
        self._routes[code] = app.router.routes[before:]
        app.openapi_schema = None

    def _unmount(self, app: FastAPI, code: str) -> None:
        gone = self._routes.pop(code)
        # Новый список, а не правка старого: запрос, который сейчас
        # перебирает роуты, дочитает свой снимок.
        app.router.routes = [
            route
            for route in app.router.routes
            if not any(route is g for g in gone)
        ]
        app.openapi_schema = None

    async def install_apps(self, codes: list[str], app: FastAPI) -> list[str]:
        """Установить приложения (с недостающими зависимостями).

        Для каждого: флаг installed → post_init (сидеры идемпотентны, это
        тот же код, что на старте). Под системной сессией и тем же
        advisory-локом, что и стартовые сидеры.
        """
        from backend.base.system.dotorm.dotorm.access import system_access

        order = self.apps.install_order(codes, self.installed)
        if not order:
            return []
        async with self.apps.db.advisory_lock(POST_INIT_LOCK_ID):
            async with system_access():
                for code in order:
                    await self._set_installed(code, True)
                    self.installed.add(code)
                    service = self.apps.get(code)
                    if service.info.get("post_init"):
                        await service.post_init(app)
        await self.apps_changed(app)
        return order

    async def uninstall_apps(
        self, codes: list[str], app: FastAPI
    ) -> list[str]:
        """Удалить приложения вместе с установленными зависимыми.

        Только флаг. Таблицы, роли, ACL и настройки не трогаем: роуты
        вырезаются, меню прячется, а повторная установка возвращает всё
        без потерь.
        """
        from backend.base.system.dotorm.dotorm.access import system_access

        order = self.apps.uninstall_order(codes, self.installed)
        if not order:
            return []
        async with system_access():
            for code in order:
                await self._set_installed(code, False)
                self.installed.discard(code)
        await self.apps_changed(app)
        return order

    async def _set_installed(self, code: str, value: bool) -> None:
        rows = await self.models.app.search(
            filter=[("code", "=", code)], fields=["id"], limit=1
        )
        if rows:
            await rows[0].update(payload=self.models.app(installed=value))

    async def apps_changed(self, app: FastAPI) -> None:
        """Флаги изменились: свои роуты — сразу, остальным воркерам — событие
        в шину chat pub/sub (обработчик там перечитывает флаги и зовёт
        sync_routers). Без шины меняется только этот процесс."""
        self.sync_routers(app)
        try:
            pubsub = self.apps.chat.chat_manager.pubsub
        except Exception:
            pubsub = None
        if pubsub is not None:
            await pubsub.publish("apps_changed", {})

    def _include_routers_from_package(
        self, app: FastAPI, package_import_path: str
    ) -> None:
        """
        Импортировать все .py-модули из пакета `<package>` (нерекурсивно)
        и подключить к FastAPI найденные APIRouter-ы:
        router_public / router_private / router_content.

        Если пакета нет — тихо пропускаем (у модуля может не быть роутов).
        """
        try:
            package = importlib.import_module(package_import_path)
        except ModuleNotFoundError:
            return

        package_path = getattr(package, "__path__", None)
        if package_path is None:
            return

        api_routers_names = [
            "router_public",
            "router_private",
            "router_content",
        ]

        for _, module_name, is_pkg in pkgutil.iter_modules(package_path):
            if is_pkg:
                continue
            module = importlib.import_module(
                f"{package_import_path}.{module_name}"
            )
            for api_router_name in api_routers_names:
                api_router = getattr(module, api_router_name, None)
                if isinstance(api_router, APIRouter):
                    self.__add_router(app, api_router)

    async def load_routers(self, app: FastAPI):
        """Динамический импорт routers из всех приложений.

        Правила:
          1. Роуты фреймворка (`core.routers`) грузятся всегда —
             это инфраструктурные endpoints поверх dotorm (onchange и т.п.).
          2. Роуты прикладных приложений — только у установленных
             (sync_routers); установка из интерфейса домонтирует остальные
             без рестарта.

        Соглашение: в файле должна быть переменная router_public,
        router_private или router_content типа APIRouter.
        """
        # Флаги «установлено» нужны и HTTP-воркерам, и cron-процессу.
        await self.load_installed()

        if self.cron_mode:
            return

        # 1. Фреймворковые роуты — всегда
        self._include_routers_from_package(
            app, "backend.base.system.core.routers"
        )

        # 2. Роуты прикладных приложений — по флагам
        self.sync_routers(app)

    async def setup_services(self):
        for app in self.apps.get_list():
            if app.info.get("service") and isinstance(app, Service):
                # В cron_mode пропускаем сервисы с cron_skip=True
                if self.cron_mode and app.info.get("cron_skip"):
                    continue
                if app.info.get("service_start_before"):
                    self.services_before.append(app)
                else:
                    self.services_after.append(app)

    async def start_services_before(self, app: FastAPI):
        "Сервисы, которые запускаются до старта приложения"
        for service in self.services_before:
            await service.startup_depends(app)

    async def start_services_after(self, app: FastAPI):
        "Сервисы, которые запускаются после старта приложения"
        for service in self.services_after:
            await service.startup_depends(app)

    async def stop_services(self, app: FastAPI):
        # Обратный порядок: сначала services_after (Chat, etc.),
        # потом services_before (DB pool) — чтобы connections были живы при shutdown
        for service in reversed(self.services_after):
            await service.shutdown(app)
        for service in reversed(self.services_before):
            await service.shutdown(app)

    async def start_post_init(self, app: FastAPI):
        """Выполнения дествия после инициализации приложения.
        Например создание данных по умолчанию, например пользователь админ"""
        from backend.base.system.dotorm.dotorm.access import (
            set_access_session,
            clear_access_session,
        )
        from backend.base.crm.security.models.sessions import SystemSession
        from backend.base.crm.users.models.users import SYSTEM_USER_ID

        # статичная папка для картинок и файлов
        app.mount(
            "/static",
            StaticFiles(
                directory=os.path.abspath(os.path.dirname(__file__))
                + "/static"
            ),
            name="static",
        )

        async with self.apps.db.advisory_lock(POST_INIT_LOCK_ID):
            # Устанавливаем системную сессию для post_init операций
            set_access_session(SystemSession(user_id=SYSTEM_USER_ID))

            try:
                # post_init — только установленных приложений: сидеры
                # неустановленного (роли, ACL, настройки) выполнит установка.
                for code in self.apps.get_names():
                    service = self.apps.get(code)
                    if service.info.get("post_init") and self.is_installed(
                        code
                    ):
                        await service.post_init(app)
                # Сидер security создал строки apps новым приложениям —
                # дальше источник правды только БД.
                await self.load_installed()
                self.sync_routers(app)
                from backend.base.system.core.system_settings import (
                    SystemSettings,
                )

                await SystemSettings.warm_cache()
            finally:
                # Очищаем системную сессию после инициализации
                clear_access_session()

    def add_handlers_errors(self, app_server: FastAPI):
        async def catch_exception_handler_500(
            request: Request, exc: Exception
        ):
            return JSONResponse(
                content={"error": "#INTERNAL_SERVER_ERROR"},
                status_code=500,
            )

        async def catch_exception_handler_fara(
            request: Request, exc: Exception
        ):
            error_data = exc.args[0]
            # Возвращаем объект с content для корректной обработки на фронтенде
            return JSONResponse(
                content={
                    "content": error_data.get("content", "UNKNOWN_ERROR"),
                    "detail": error_data.get("detail"),
                },
                status_code=error_data.get("status_code", 400),
            )

        app_server.add_exception_handler(
            Exception, catch_exception_handler_500
        )
        app_server.add_exception_handler(
            environment.FaraException, catch_exception_handler_fara
        )

        for app in self.apps.get_list():
            app.handler_errors(app_server)

    def __init__(self):
        self.settings: Settings
        self.models: Models
        self.apps: Apps
        self.services_before: list[Service] = []
        self.services_after: list[Service] = []
        self.post_init = []
        self.cron_mode: bool = False
        # Коды установленных приложений (см. load_installed) и роуты,
        # смонтированные в этом процессе, по кодам (см. sync_routers).
        self.installed: set[str] = set()
        self._routes: dict[str, list] = {}

    # def __new__(cls):
    #     if not hasattr(cls, "instance"):
    #         cls.instance = super().__new__(cls)
    #     return cls.instance


env = Environment()
