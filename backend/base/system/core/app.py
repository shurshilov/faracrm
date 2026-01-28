import logging
from typing import NotRequired, TypedDict
from fastapi import FastAPI

log = logging.getLogger(__package__)


class AppInfo(TypedDict):
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


# Импортируем после определения AppInfo чтобы избежать циклических импортов
from backend.base.crm.security.acl_post_init_mixin import ACLPostInitMixin


class App(ACLPostInitMixin):
    """
    Базовый класс приложения.

    Включает ACL инициализацию через BASE_USER_ACL и ROLE_ACL.

    Пример:
        from backend.base.crm.security.acl_post_init_mixin import ACL, ACLPerms

        class LeadsApp(App):
            BASE_USER_ACL = {
                "lead": ACL.FULL,
                "lead_stage": ACLPerms(create=True, read=True, update=True, delete=False),
            }

            ROLE_ACL = {
                "viewer": {
                    "lead": ACL.READ_ONLY,
                },
            }
    """

    info: AppInfo

    def __init__(self) -> None:
        super().__init__()
        log.info(
            f"Start App: {self.info.get('name')} {self.info.get('version')}"
        )

    async def post_init(self, app: FastAPI):
        """
        Инициализация приложения после старта.

        Системная сессия уже установлена в Environment.start_post_init().
        Автоматически создаёт ACL из BASE_USER_ACL и ROLE_ACL.
        Наследники могут переопределять этот метод, вызывая super().
        """
        # Автоматическая инициализация ACL
        if self.BASE_USER_ACL or self.ROLE_ACL:
            await self._init_acl(app.state.env)

    def handler_errors(self, app_server: FastAPI):
        ...
        # async def catch_exception_handler_500(request: Request, exc: Exception):
        #     return JSONResponse(
        #         content={"error": "#INTERNAL_SERVER_ERROR"},
        #         status_code=500,
        #     )

        # app_server.add_exception_handler(Exception, catch_exception_handler_500)
