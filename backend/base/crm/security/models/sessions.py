from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING

from backend.base.crm.auth_token.session_cache import CachedSession
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

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.auth_token.session_cache import SessionCache
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


class AnonymousSession:
    """
    Анонимная сессия для публичных эндпоинтов (без авторизации).

    Используется в public-роутах вместо None, чтобы DotORM применял
    security-правила вместо тихого допуска ко всему.

    user_id ссылается на реальную запись в БД (id=4, login="anonymous"),
    которую UserApp.post_init создаёт при инициализации. Это позволит
    в будущем настраивать ACL/Rules для anonymous через UI как для
    обычной роли. Сейчас доступ ограничен whitelist'ом таблиц,
    передаваемым через allowed_tables — каждый public-роутер
    декларирует ровно те таблицы которые ему нужны
    (принцип минимальных привилегий). WRITE запрещён всегда.
    """

    def __init__(self, allowed_tables: frozenset[str] = frozenset()):
        """
        Args:
            allowed_tables: имена таблиц (__table__) к которым
                разрешён READ. WRITE для anonymous полностью запрещён
                независимо от этого списка.
        """
        from backend.base.crm.users.models.users import (
            User,
            ANONYMOUS_USER_ID,
        )

        self.user_id = User(
            id=ANONYMOUS_USER_ID,
            is_admin=False,
            name="Anonymous",
            login="anonymous",
            password_hash="",
            password_salt="",
        )
        self.allowed_tables: frozenset[str] = allowed_tables


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

    # Дефолты лимитов активных сессий на пользователя.
    # Переопределяются через system_settings:
    #   auth.max_active_sessions       — порог, при превышении чистим
    #   auth.sessions_cleanup_batch    — сколько самых старых закрывать
    DEFAULT_MAX_ACTIVE_SESSIONS = 50
    DEFAULT_SESSIONS_CLEANUP_BATCH = 10

    @classmethod
    async def enforce_session_limit(cls, user_id: int) -> int:
        """
        Ограничить число активных сессий пользователя.

        Если активных > max_active_sessions (дефолт 50) — деактивировать
        sessions_cleanup_batch самых старых (дефолт 10).
        Вызывается после успешного создания сессии при логине.

        Returns:
            Количество деактивированных сессий (0 если лимит не превышен).
        """
        max_active = int(
            await env.models.system_settings.get_value(
                "auth.max_active_sessions",
                cls.DEFAULT_MAX_ACTIVE_SESSIONS,
            )  # type: ignore
        )
        cleanup_batch = int(
            await env.models.system_settings.get_value(
                "auth.sessions_cleanup_batch",
                cls.DEFAULT_SESSIONS_CLEANUP_BATCH,
            )  # type: ignore
        )
        db_session = cls._get_db_session()

        # Одним SQL: посчитать активные, и если > max — деактивировать
        # cleanup_batch самых старых. CTE, никаких race-ов.
        stmt = """
            WITH active_count AS (
                SELECT COUNT(*)::int AS c FROM sessions
                WHERE user_id = %s AND active = true
            ),
            to_deactivate AS (
                SELECT id FROM sessions
                WHERE user_id = %s AND active = true
                ORDER BY create_datetime ASC
                LIMIT %s
            ),
            did_update AS (
                UPDATE sessions
                SET active = false
                WHERE id IN (SELECT id FROM to_deactivate)
                  AND (SELECT c FROM active_count) > %s
                RETURNING id
            )
            SELECT COUNT(*)::int AS cnt,
                   ARRAY_AGG(id) AS ids
            FROM did_update
        """
        result = await db_session.execute(
            stmt,
            [user_id, user_id, cleanup_batch, max_active],
        )
        if not result:
            return 0

        row = result[0]
        deactivated = int(row.get("cnt") or 0)
        ids = row.get("ids") or []

        # Инвалидируем SessionCache на всех воркерах если что-то деактивировали
        if deactivated > 0 and ids and env.apps.auth.session_cache_enabled:
            await cls.publish_revoked(list(ids))

        return deactivated

    @classmethod
    async def cron_expire_sessions(cls) -> dict:
        """
        Крон: пометить все протухшие активные сессии неактивными.
        active = true AND expired_datetime < now() → active = false.

        Returns:
            {"deactivated": N} — сколько сессий закрыто.
        """
        db_session = cls._get_db_session()
        stmt = """
            WITH expired AS (
                UPDATE sessions
                SET active = false
                WHERE active = true
                  AND expired_datetime IS NOT NULL
                  AND expired_datetime < now()
                RETURNING id
            )
            SELECT COUNT(*)::int AS cnt,
                   ARRAY_AGG(id) AS ids
            FROM expired
        """
        result = await db_session.execute(stmt)
        if not result:
            return {"deactivated": 0}

        row = result[0]
        cnt = int(row.get("cnt") or 0)
        ids = row.get("ids") or []

        if ids and env.apps.auth.session_cache_enabled:
            await cls.publish_revoked(list(ids))

        return {"deactivated": cnt}

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
    # без изменений. Выбор между версиями делается на уровне env.apps.auth
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
        cache: "SessionCache" = env.apps.auth.session_cache
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

        cache = env.apps.auth.session_cache
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
                for sid in session_ids:
                    await env.apps.auth.session_cache.revoke(sid)
            except Exception as e:
                logger.warning("Failed to revoke session: %s", e)
            return
        await pubsub.publish(
            "session_revoked",
            {"session_ids": list(session_ids)},
        )
