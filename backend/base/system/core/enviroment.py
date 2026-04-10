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

    def is_installed(self, module_name: str):
        """Установлен модуль или нет."""
        return module_name in self.apps.get_names()

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
          2. Роуты прикладных приложений грузятся только для тех,
             что зарегистрированы в Apps. Имя пакета берётся из класса
             самого App через __module__, а не из пути файла.

        Соглашение: в файле должна быть переменная router_public,
        router_private или router_content типа APIRouter.
        """
        if self.cron_mode:
            return

        # 1. Фреймворковые роуты — всегда
        self._include_routers_from_package(
            app, "backend.base.system.core.routers"
        )

        # 2. Роуты прикладных приложений — по списку Apps
        for installed_app in self.apps.get_list():
            app_module = installed_app.__class__.__module__
            # app_module например "backend.base.system.administration.app"
            package_import_path = app_module.rsplit(".", 1)[0] + ".routers"
            self._include_routers_from_package(app, package_import_path)

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

        # Устанавливаем системную сессию для post_init операций
        set_access_session(SystemSession(user_id=SYSTEM_USER_ID))

        try:
            # Выполняем post_init всех приложений
            for service in self.apps.get_list():
                if service.info.get("post_init"):
                    await service.post_init(app)
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

    # def __new__(cls):
    #     if not hasattr(cls, "instance"):
    #         cls.instance = super().__new__(cls)
    #     return cls.instance


env = Environment()
