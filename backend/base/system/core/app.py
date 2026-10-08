import logging
from typing import ClassVar, NotRequired, TypedDict, TYPE_CHECKING

from backend.base.system.dotorm.dotorm.access import SudoAccessor

if TYPE_CHECKING:
    from fastapi import FastAPI

log = logging.getLogger(__package__)


class AppInfo(TypedDict):
    ui_menu: NotRequired[bool]
    ui_menu_name: NotRequired[str]
    name: str
    summary: str
    author: str
    category: str
    version: str
    license: str
    depends: list
    service: NotRequired[bool]
    service_start_before: NotRequired[bool]
    service_aliase: NotRequired[str]
    sequence: NotRequired[int]
    post_init: NotRequired[bool]
    cron_skip: NotRequired[bool]
    # Ключи auto_install и core читает модуль apps_install (установка и
    # удаление из интерфейса); без него активно всё из project_setup.
    # auto_install (по умолчанию True) — ставить приложение само, когда оно
    # впервые появилось в коде и все его depends установлены. False —
    # ждать, пока админ установит его руками (маркетплейс, оплата и т.п.).
    # Правило работает один раз: у приложения со строкой в apps
    # состояние берётся из БД.
    auto_install: NotRequired[bool]
    # core — удалить нельзя (users, auth, company…). Сервисы (service=True)
    # считаются core автоматически: это инфраструктура, а не функционал.
    # Сервис с core=False — отключаемый: стартует, только когда установлен,
    # удаление зовёт его shutdown (AppsInstallService.sync_services). Флаги
    # установки читаются на старте apps_install (среди services_before),
    # поэтому такой сервис — без service_start_before.
    core: NotRequired[bool]
    # Публичная страница модуля, на которую отправляется гость с корня сайта
    # вместо формы входа (маркетплейс → "/market"). Отдаётся фронту в
    # /public/config как public_home — первого установленного модуля.
    public_home: NotRequired[str]


class AppHook:
    """
    Поведение, которое другой модуль добавляет всем приложениям: ядро
    зовёт методы, реализацию даёт модуль (как AccessChecker у dotorm).
    Регистрация — App.hooks.append(MyHook()) в app.py модуля.
    """

    async def post_init(self, service: "App", app: "FastAPI") -> None:
        """Из App.post_init — там, где приложение зовёт super().post_init()."""


class App:
    """
    Базовый класс приложения.

    Права своих моделей модуль объявляет атрибутами BASE_USER_ACL и
    ROLE_ACL — строки по ним создаёт хук security (ACLHook,
    security/acl_post_init_mixin.py); ядро о правах не знает.
    """

    info: AppInfo

    # Хуки других модулей (AppHook), вызываются базовым post_init.
    hooks: ClassVar[list[AppHook]] = []

    # Как у моделей: `await service.sudo().post_init(app)` — сидеры модуля
    # с полным доступом при установке из интерфейса (apps_install).
    sudo = SudoAccessor()

    def __init__(self) -> None:
        super().__init__()
        log.info(
            "Start App: %s %s",
            self.info.get("name"),
            self.info.get("version"),
        )

    async def post_init(self, app: "FastAPI"):
        """
        Инициализация приложения после старта.

        Системная сессия уже установлена в Environment.start_post_init().
        Наследники переопределяют этот метод, вызывая super() — он
        выполняет хуки (security создаёт права, поэтому роли модуля — до
        super()).
        """
        for hook in App.hooks:
            await hook.post_init(self, app)

    def handler_errors(self, app_server: "FastAPI"):
        """Регистрация обработчиков ошибок приложения (override в наследниках)."""
        # async def catch_exception_handler_500(request: Request, exc: Exception):
        #     return JSONResponse(
        #         content={"error": "#INTERNAL_SERVER_ERROR"},
        #         status_code=500,
        #     )

        # app_server.add_exception_handler(Exception, catch_exception_handler_500)
