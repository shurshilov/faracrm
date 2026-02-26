import importlib
import os
import platform
from glob import glob
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

    async def load_routers(self, app: FastAPI):
        """Динамический импорт routers из всех приложений
        (папок) и подпапках routers.
        Соглашение - router должен быть обьявлен как
        переменная router_public или router_private.
        Все роуты должны находиться в папке routers.
        """
        if self.cron_mode:
            return
        routers = glob(f"./**/**/**/**/routers/**") + glob(
            f"./**/**/**/**/routers/**/*"
        )
        routers = [
            router
            for router in routers
            if router.endswith(".py") and not router.endswith("__init__.py")
        ]
        for file_path in routers:
            module_name = file_path.split(self.spliter)[4]
            if self.is_installed(module_name):
                import_path = self.get_python_import(file_path)
                module = importlib.import_module(import_path)

                # добавить публичные маршруты
                router_public = getattr(module, "router_public", None)
                if isinstance(router_public, APIRouter):
                    self.__add_router(app, router_public)
                # добавить приватные (с аутентификацией) маршруты
                router_private = getattr(module, "router_private", None)
                if isinstance(router_private, APIRouter):
                    self.__add_router(app, router_private)
                # добавить маршруты для бинарного контента (cookie auth)
                router_content = getattr(module, "router_content", None)
                if isinstance(router_content, APIRouter):
                    self.__add_router(app, router_content)

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
        for service in self.services_before + self.services_after:
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings: Settings
        self.models: Models
        self.apps: Apps
        self.services_before: list[Service] = []
        self.services_after: list[Service] = []
        self.post_init = []
        self.cron_mode: bool = False

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance


env = Environment()
