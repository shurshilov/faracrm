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
        """Валидация через двойной токен (Token Binding):
        1. Bearer token из Authorization header (обязателен)s
        2. cookie_token из HttpOnly cookie (обязателен)

        XSS может украсть Bearer из localStorage, но не может прочитать
        HttpOnly cookie - украденный токен бесполезен.

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

        # Cookie token обязателен
        env: Environment = request.app.state.env
        cookie_token = request.cookies.get(env.settings.auth.cookie_name)
        if not cookie_token:
            raise SessionErrorFormat()

        session = await env.models.session.session_check(
            credentials.credentials, cookie_token=cookie_token
        )
        request.state.session = session

        # Устанавливаем сессию для проверки доступа в DotORM
        set_access_session(session)

        return session

    @staticmethod
    async def verify_access_by_cookie(request: Request):
        """Валидация только через HttpOnly cookie (для бинарного контента).

        Используется для роутов где невозможно передать Authorization header:
        <img src="...">, <a href="...">, <audio src="...">, window.open()

        Guard cookie содержит token привязанный к сессии — проверяем его
        через обратный lookup: cookie_token - session.
        """
        env: Environment = request.app.state.env
        cookie_token = request.cookies.get(env.settings.auth.cookie_name)
        if not cookie_token:
            raise SessionErrorFormat()

        session = await env.models.session.session_check_by_cookie(
            cookie_token
        )
        request.state.session = session
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
