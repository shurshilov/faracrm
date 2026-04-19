from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Datetime,
    Field,
    Integer,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.crm.security.exceptions import AuthException

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
from backend.base.system.core.enviroment import env

# class _SystemUser:
#     """Системный пользователь для post_init операций."""

#     def __init__(self, user_id: int):
#         self.id = user_id
#         self.is_admin = True

#     def json(self) -> dict:
#         return {"id": self.id, "is_admin": True}


class SystemSession:
    """
    Системная сессия для инициализации.

    Используется в post_init для выполнения операций
    от имени системного пользователя.

    Args:
        user_id: ID системного пользователя
    """

    def __init__(self, user_id: int):
        from backend.base.crm.users.models.users import User

        self.user_id = User(
            id=user_id,
            is_admin=True,
            name="System",
            login="system",
            password_hash="",
            password_salt="",
        )


class Session(DotModel):
    __table__ = "sessions"

    def get_lang(self) -> str:
        """Контракт DotORM: код текущего языка."""
        if (
            self.user_id
            and self.user_id.lang_id
            and not isinstance(self.user_id.lang_id, Field)
        ):
            return self.user_id.lang_id.code or "en"
        return "en"

    # Значение по умолчанию — 1 день (используется если system_settings недоступен)
    DEFAULT_TTL = 60 * 60 * 24 * 1

    id: int = Integer(primary_key=True)
    active: bool = Boolean(default=True)
    user_id: "User" = Many2one(relation_table=lambda: env.models.user)
    token: str = Char(max_length=256, index=True)
    cookie_token: str | None = Char(
        max_length=256,
        index=True,
        description="HttpOnly cookie token for XSS protection (Token Binding)",
    )
    ttl: int = Integer()
    expired_datetime: datetime | None = Datetime()

    create_datetime: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )
    create_user_id: "User" = Many2one(relation_table=lambda: env.models.user)
    update_datetime: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )
    update_user_id: "User" = Many2one(relation_table=lambda: env.models.user)

    # Последняя активность пользователя (обновляется через WS ping).
    # Пользователь считается онлайн если last_activity > now() - 120 секунд.
    last_activity: datetime | None = Datetime(index=True)

    @classmethod
    async def get_ttl(cls) -> int:
        """Получить TTL сессии из системных настроек."""
        try:
            value = await env.models.system_settings.get_value(
                "auth.session_ttl", cls.DEFAULT_TTL
            )
            return int(value)
        except Exception:
            return cls.DEFAULT_TTL

    @hybridmethod
    async def session_check(self, token: str, cookie_token: str | None = None):
        """Метод проверяет валидность сессии.
        1. Проверить существование активной сессии по токену
        2. Проверить истекла сессии или нет
        3. Проверить cookie_token (Token Binding — обязателен)
        """
        session = self._get_db_session()

        # Прямой SQL для получения сессии с данными пользователя
        stmt = """
            SELECT
                s.id,
                s.ttl,
                s.create_datetime,
                s.expired_datetime,
                s.active,
                s.cookie_token,
                u.id as user_id,
                u.is_admin,
                u.lang_id,
                u.name,
                l.code as lang_code
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            LEFT JOIN language l ON u.lang_id = l.id
            WHERE s.token = %s AND s.active = true
            LIMIT 1
        """

        result = await session.execute(stmt, [token])

        if not result:
            raise AuthException.SessionNotExist()

        session_id = result[0]
        now = datetime.now(timezone.utc)
        # expired = session_id["create_datetime"] + timedelta(
        #     seconds=session_id["ttl"]
        # )
        expired = session_id["expired_datetime"]

        if expired < now:
            # Деактивируем сессию
            await session.execute(
                "UPDATE sessions SET active = false WHERE id = %s",
                [session_id["id"]],
            )
            raise AuthException.SessionExpired()

        # Token Binding: cookie_token обязателен.
        # На будущее для мобильных: добавить client_type + device_id.
        stored_cookie = session_id.get("cookie_token")
        if (
            not stored_cookie
            or not cookie_token
            or cookie_token != stored_cookie
        ):
            raise AuthException.SessionNotExist()

        # Создаём объект сессии с user_id содержащим is_admin
        session_obj = Session(
            id=session_id["id"],
            ttl=session_id["ttl"],
            create_datetime=session_id["create_datetime"],
            active=session_id["active"],
            user_id=env.models.user(
                id=session_id["user_id"],
                is_admin=session_id["is_admin"],
                name=session_id["name"],
                lang_id=env.models.language(
                    id=session_id["lang_id"],
                    code=session_id["lang_code"],
                ),
            ),
        )

        return session_obj

    @hybridmethod
    async def session_check_by_cookie(self, cookie_token: str):
        """Проверка сессии по cookie_token (из HttpOnly cookie).

        Используется для бинарного контента (attachments), где невозможно
        передать Authorization header (<img src>, <a href>).
        """
        session = self._get_db_session()

        stmt = """
            SELECT
                s.id,
                s.ttl,
                s.create_datetime,
                s.expired_datetime,
                s.active,
                u.id as user_id,
                u.is_admin,
                u.name
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.cookie_token = %s AND s.active = true
            LIMIT 1
        """

        result = await session.execute(stmt, [cookie_token])

        if not result:
            raise AuthException.SessionNotExist()

        session_id = result[0]
        now = datetime.now(timezone.utc)
        expired = session_id["expired_datetime"]

        if expired < now:
            await session.execute(
                "UPDATE sessions SET active = false WHERE id = %s",
                [session_id["id"]],
            )
            raise AuthException.SessionExpired()

        session_obj = Session(
            id=session_id["id"],
            ttl=session_id["ttl"],
            create_datetime=session_id["create_datetime"],
            active=session_id["active"],
            user_id=env.models.user(
                id=session_id["user_id"],
                is_admin=session_id["is_admin"],
                name=session_id["name"],
            ),
        )

        return session_obj

    # ================================================================
    # CACHED-ВЕРСИИ: параллельные реализации проверки через SessionCache.
    # Оригинальные session_check / session_check_by_cookie оставлены выше
    # без изменений. Выбор между версиями делается на уровне AuthTokenApp
    # через флаг auth.session_cache_enabled (читается при старте).
    # ================================================================

    @hybridmethod
    async def session_check_cached(
        self, token: str, cookie_token: str | None = None
    ):
        """
        Cached-версия session_check: сначала смотрит в SessionCache,
        при cache miss — идёт в БД и кладёт результат в кэш.
        """
        from backend.base.crm.auth_token.session_cache import (
            SessionCache,
        )
        from backend.base.crm.auth_token.app import AuthTokenApp

        cache: SessionCache = AuthTokenApp.session_cache
        cached = await cache.get_by_token(token)

        if cached is None:
            cached = await self._fetch_session_from_db(token, cache)
            if cached is None:
                raise AuthException.SessionNotExist()

        if cached.revoked:
            raise AuthException.SessionNotExist()

        now = datetime.now(timezone.utc)
        if cached.expired_datetime < now:
            session = self._get_db_session()
            await session.execute(
                "UPDATE sessions SET active = false WHERE id = %s",
                [cached.session_id],
            )
            await cache.drop_by_token(token)
            await Session.publish_revoked([cached.session_id])
            raise AuthException.SessionExpired()

        # Token Binding: cookie_token обязателен.
        if (
            not cached.cookie_token
            or not cookie_token
            or cookie_token != cached.cookie_token
        ):
            raise AuthException.SessionNotExist()

        return Session(
            id=cached.session_id,
            ttl=cached.ttl,
            create_datetime=cached.create_datetime,
            active=True,
            user_id=env.models.user(
                id=cached.user_id,
                is_admin=cached.is_admin,
                name=cached.user_name,
                lang_id=env.models.language(
                    id=cached.lang_id,
                    code=cached.lang_code,
                ),
            ),
        )

    @hybridmethod
    async def session_check_by_cookie_cached(self, cookie_token: str):
        """
        Cached-версия session_check_by_cookie.
        """
        from backend.base.crm.auth_token.app import AuthTokenApp

        cache = AuthTokenApp.session_cache
        cached = await cache.get_by_cookie(cookie_token)

        if cached is None:
            cached = await self._fetch_session_by_cookie_from_db(
                cookie_token, cache
            )
            if cached is None:
                raise AuthException.SessionNotExist()

        if cached.revoked:
            raise AuthException.SessionNotExist()

        now = datetime.now(timezone.utc)
        if cached.expired_datetime < now:
            session = self._get_db_session()
            await session.execute(
                "UPDATE sessions SET active = false WHERE id = %s",
                [cached.session_id],
            )
            await cache.drop_by_token(cached.token or "")
            await Session.publish_revoked([cached.session_id])
            raise AuthException.SessionExpired()

        return Session(
            id=cached.session_id,
            ttl=cached.ttl,
            create_datetime=cached.create_datetime,
            active=True,
            user_id=env.models.user(
                id=cached.user_id,
                is_admin=cached.is_admin,
                name=cached.user_name,
            ),
        )

    async def _fetch_session_from_db(self, token: str, cache):
        """Cache miss для session_check_cached: загружает из БД."""
        from backend.base.crm.auth_token.session_cache import CachedSession

        session = self._get_db_session()
        stmt = """
            SELECT
                s.id,
                s.ttl,
                s.create_datetime,
                s.expired_datetime,
                s.active,
                s.token,
                s.cookie_token,
                u.id as user_id,
                u.is_admin,
                u.lang_id,
                u.name,
                l.code as lang_code
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            LEFT JOIN language l ON u.lang_id = l.id
            WHERE s.token = %s AND s.active = true
            LIMIT 1
        """
        result = await session.execute(stmt, [token])
        if not result:
            return None

        row = result[0]
        cached = CachedSession(
            session_id=row["id"],
            user_id=row["user_id"],
            is_admin=row["is_admin"],
            user_name=row["name"],
            lang_id=row["lang_id"],
            lang_code=row["lang_code"],
            cookie_token=row.get("cookie_token"),
            token=row.get("token"),
            expired_datetime=row["expired_datetime"],
            ttl=row["ttl"],
            create_datetime=row["create_datetime"],
        )
        await cache.put(cached)
        return cached

    async def _fetch_session_by_cookie_from_db(self, cookie_token: str, cache):
        """Cache miss для session_check_by_cookie_cached."""
        from backend.base.crm.auth_token.session_cache import CachedSession

        session = self._get_db_session()
        stmt = """
            SELECT
                s.id,
                s.ttl,
                s.create_datetime,
                s.expired_datetime,
                s.active,
                s.token,
                s.cookie_token,
                u.id as user_id,
                u.is_admin,
                u.name
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.cookie_token = %s AND s.active = true
            LIMIT 1
        """
        result = await session.execute(stmt, [cookie_token])
        if not result:
            return None

        row = result[0]
        cached = CachedSession(
            session_id=row["id"],
            user_id=row["user_id"],
            is_admin=row["is_admin"],
            user_name=row["name"],
            lang_id=None,
            lang_code=None,
            cookie_token=row.get("cookie_token"),
            token=row.get("token"),
            expired_datetime=row["expired_datetime"],
            ttl=row["ttl"],
            create_datetime=row["create_datetime"],
        )
        await cache.put(cached)
        return cached

    @classmethod
    async def publish_revoked(cls, session_ids: list[int]) -> None:
        """
        Опубликовать событие revoke в pg_notify. Все воркеры инвалидируют
        свой SessionCache. Переиспользуем pubsub из chat_manager.
        Без-op если кэш выключен (no-op полезен чтобы код не падал).
        """
        if not session_ids:
            return
        try:
            pubsub = env.apps.chat.chat_manager.pubsub
        except Exception:
            pubsub = None
        if pubsub is None:
            # Нет pubsub (тесты без chat-app) — инвалидируем локально
            try:
                from backend.base.crm.auth_token.app import AuthTokenApp

                for sid in session_ids:
                    await AuthTokenApp.session_cache.revoke(sid)
            except Exception:
                pass
            return
        await pubsub.publish(
            "session_revoked",
            {"session_ids": list(session_ids)},
        )
