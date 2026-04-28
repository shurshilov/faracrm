from fastapi import FastAPI, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.base.system.auth.strategy_abstract import AuthStrategyAbstract
from backend.base.system.core.app import App
from backend.base.system.core.enviroment import Environment
from backend.base.system.dotorm.dotorm.access import set_access_session
from backend.base.crm.security.models.sessions import (
    SystemSession,
    AnonymousSession,
)
from backend.base.crm.users.models.users import SYSTEM_USER_ID
from backend.base.crm.security.exceptions.AuthException import (
    SessionErrorFormat,
    SessionExpired,
    SessionNotExist,
)
from .session_cache import SessionCache


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
        "post_init": True,
    }

    session_cache: SessionCache = SessionCache()
    session_cache_enabled: bool = False

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        # Настройки лимита активных сессий на пользователя.
        # cache_ttl=-1 — прогреваются в SystemSettings.warm_cache().
        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": "auth.session_cache_enabled",
                    "value": {"value": True},
                    "description": "Включено ли кеширование сессий",
                    "module": "auth_token",
                    "is_system": True,
                    "cache_ttl": -1,
                },
                {
                    "key": "auth.max_active_sessions",
                    "value": {"value": 50},
                    "description": (
                        "Максимум активных сессий на пользователя. "
                        "При превышении самые старые деактивируются при "
                        "следующем логине."
                    ),
                    "module": "auth_token",
                    "is_system": True,
                    "cache_ttl": -1,
                },
                {
                    "key": "auth.sessions_cleanup_batch",
                    "value": {"value": 10},
                    "description": (
                        "Сколько самых старых сессий закрывать при превышении "
                        "лимита max_active_sessions."
                    ),
                    "module": "auth_token",
                    "is_system": True,
                    "cache_ttl": -1,
                },
            ]
        )
        value = await env.models.system_settings.get_value(
            "auth.session_cache_enabled", False
        )
        if value:
            AuthTokenApp.session_cache_enabled = value

        # Cron: ежечасно деактивировать протухшие сессии.
        await env.models.cron_job.create_or_update(
            env=env,
            name="Auth: deactivate expired sessions",
            code=("result = await env.models.session.cron_expire_sessions()"),
            interval_number=1,
            interval_type="hours",
            active=True,
            priority=50,
        )

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

        # Флаг session_cache_enabled прочитан один раз при старте (post_init)
        # из system_settings. Менять → рестарт.
        if AuthTokenApp.session_cache_enabled:
            session = await env.models.session.session_check_cached(
                credentials.credentials, cookie_token=cookie_token
            )
        else:
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

        if AuthTokenApp.session_cache_enabled:
            session = await env.models.session.session_check_by_cookie_cached(
                cookie_token
            )
        else:
            session = await env.models.session.session_check_by_cookie(
                cookie_token
            )

        request.state.session = session
        set_access_session(session)

        return session

    @staticmethod
    def use_anonymous_session(allowed_tables: list[str]):
        """
        Factory: возвращает FastAPI dependency для public-эндпоинтов.

        Каждый public-роутер декларирует список таблиц к которым
        разрешён READ для анонимного пользователя — принцип
        минимальных привилегий. WRITE запрещён всегда.

        Применение:
            router_public = APIRouter(
                dependencies=[
                    Depends(AuthTokenApp.use_anonymous_session(
                        ["company", "attachments"]
                    )),
                ],
            )

        Args:
            allowed_tables: список имён таблиц (__table__) к которым
                разрешён READ. Передаются в AnonymousSession и
                проверяются в SecurityAccessChecker.

        Returns:
            async dependency-функцию которую FastAPI вызовет на каждом
            запросе к этому роутеру.
        """
        # Замораживаем список для безопасности (frozenset не мутабелен).
        tables = frozenset(allowed_tables)

        async def _dep():
            # Создаём сессию заново на каждый запрос — её allowed_tables
            # связан с конкретным роутером, а не глобален.
            set_access_session(AnonymousSession(allowed_tables=tables))

        return _dep

    @staticmethod
    async def use_system_session():
        """
        Dependency для public-эндпоинтов которые **доверены** и нуждаются
        в полном доступе: webhook'и (от телефонии), OAuth callbacks (от
        Google), signin (создаёт сессию пользователю).

        Использовать ТОЛЬКО когда:
        1. Эндпоинт принимает данные от доверенного источника (или
           подтверждает подпись/токен внутри handler);
        2. Логика handler'а сама проверяет права (например, signin
           проверяет пароль перед созданием session).
        """
        set_access_session(SystemSession(user_id=SYSTEM_USER_ID))

    def handler_errors(self, app_server: FastAPI):
        async def catch_exception_handler_auth(
            request: Request, exc: Exception
        ):
            env: "Environment" = request.app.state.env
            # если ошибка связанная с аутентификацией
            response = JSONResponse(
                # content={"error": "#FORBIDDEN"}, status_code=401
                content={"error": "#UNAUTHORIZED"},
                status_code=401,
            )

            # удаляем куку
            response.delete_cookie(
                key=env.settings.auth.cookie_name,
                httponly=True,
                path="/",
                secure=env.settings.auth.cookie_secure,
                samesite=env.settings.auth.cookie_samesite,
            )

            return response

        app_server.add_exception_handler(
            SessionNotExist, catch_exception_handler_auth
        )
        app_server.add_exception_handler(
            SessionExpired, catch_exception_handler_auth
        )
        app_server.add_exception_handler(
            SessionErrorFormat, catch_exception_handler_auth
        )
