# Copyright 2025 FARA CRM
# Auth - in-memory session cache with pg_notify-based invalidation

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


# Ключ в system_settings. Значение: bool/str "true"/"false"/"1"/"0".
SETTING_KEY = "auth.session_cache_enabled"


@dataclass
class CachedSession:
    """Слепок данных сессии + присоединённых полей user/language.
    Позволяет собрать Session-объект без хождения в БД.
    """

    session_id: int
    user_id: int
    is_admin: bool
    user_name: str
    lang_id: int | None
    lang_code: str | None
    cookie_token: str | None
    token: str | None
    expired_datetime: datetime
    ttl: int
    create_datetime: datetime
    revoked: bool = False


class SessionCache:
    """
    In-memory кэш сессий для избежания походов в БД на каждый verify.

    Инвалидация через pg_notify: при logout / revoke публикуется событие
    session_revoked, воркеры помечают запись как revoked.

    Два индекса доступа: token и cookie_token — обе функции проверки
    (Bearer+cookie и только cookie) ходят через один и тот же кэш.
    """

    def __init__(self):
        self._by_token: dict[str, CachedSession] = {}
        self._by_cookie: dict[str, CachedSession] = {}
        self._by_session_id: dict[int, CachedSession] = {}
        self._lock = asyncio.Lock()

    async def get_by_token(self, token: str) -> CachedSession | None:
        async with self._lock:
            return self._by_token.get(token)

    async def get_by_cookie(self, cookie_token: str) -> CachedSession | None:
        async with self._lock:
            return self._by_cookie.get(cookie_token)

    async def put(self, cached: CachedSession) -> None:
        async with self._lock:
            # Если по session_id уже была запись — вычищаем её старые индексы,
            # чтобы при ротации tokens не оставалось мусора.
            prev = self._by_session_id.get(cached.session_id)
            if prev is not None:
                if prev.token and prev.token != cached.token:
                    self._by_token.pop(prev.token, None)
                if (
                    prev.cookie_token
                    and prev.cookie_token != cached.cookie_token
                ):
                    self._by_cookie.pop(prev.cookie_token, None)

            if cached.token:
                self._by_token[cached.token] = cached
            if cached.cookie_token:
                self._by_cookie[cached.cookie_token] = cached
            self._by_session_id[cached.session_id] = cached

    async def revoke(self, session_id: int) -> str | None:
        """
        Пометить запись revoked и вернуть token для принудительного закрытия
        WS (если есть). Вызывается из pg_notify handler.
        """
        async with self._lock:
            cached = self._by_session_id.pop(session_id, None)
            if cached is None:
                return None
            cached.revoked = True
            if cached.token:
                self._by_token.pop(cached.token, None)
            if cached.cookie_token:
                self._by_cookie.pop(cached.cookie_token, None)
            logger.debug("SessionCache: session %s revoked", session_id)
            return cached.token

    async def drop_by_token(self, token: str) -> None:
        async with self._lock:
            cached = self._by_token.pop(token, None)
            if cached is not None:
                self._by_session_id.pop(cached.session_id, None)
                if cached.cookie_token:
                    self._by_cookie.pop(cached.cookie_token, None)

    async def clear(self) -> None:
        async with self._lock:
            self._by_token.clear()
            self._by_cookie.clear()
            self._by_session_id.clear()

    def size(self) -> int:
        return len(self._by_session_id)
