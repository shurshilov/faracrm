from fastapi import FastAPI, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


from backend.base.system.auth.strategy_abstract import AuthStrategyAbstract
from backend.base.system.core.app import App
from backend.base.system.core.enviroment import Environment
from backend.base.system.dotorm.dotorm.access import set_access_session
from backend.base.crm.security.exceptions.AuthException import (
    SessionErrorFormat,
    SessionExpired,
    SessionNotExist,
)


class AuthTokenApp(App, AuthStrategyAbstract):
    """
    App auth
    """

    info = {
        "name": "Auth manager",
        "summary": "This module allow authentificate",
        "author": "Artem Shurshilov <shurshilov.a@yandex.ru>",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        # TODO: добавить зависимость сессии
        "depends": ["security"],
    }

    @staticmethod
    async def verify_access(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Security(
            HTTPBearer(auto_error=False)
        ),
    ):
        """Валидация токена, из http заголовка Authorization, со схемой Bearer.

        Arguments:
            credentials -- credentials (схема и токен для проверки)

        Raises:
            AuthException.SessionNotExist: сессия не существует
            AuthException.SessionExpired: сессия истекла
            AuthException.SessionErrorFormat: сессия не получена
            клиент передал пустые аутентификационные данные или не в том формате
        """

        if not credentials:
            raise SessionErrorFormat()
        env: Environment = request.app.state.env

        session = await env.models.session.session_check(
            credentials.credentials
        )
        request.state.session = session

        # Устанавливаем сессию для проверки доступа в DotORM
        set_access_session(session)

        return session

    def handler_errors(self, app_server: FastAPI):
        async def catch_exception_handler_auth(
            request: Request, exc: Exception
        ):
            # если ошибка связанная с аутентификацией
            return JSONResponse(
                content={"error": "#FORBIDDEN"}, status_code=401
            )

        app_server.add_exception_handler(
            SessionNotExist, catch_exception_handler_auth
        )
        app_server.add_exception_handler(
            SessionExpired, catch_exception_handler_auth
        )
        app_server.add_exception_handler(
            SessionErrorFormat, catch_exception_handler_auth
        )
