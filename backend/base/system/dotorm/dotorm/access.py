"""
Контекст доступа для DotORM.

Политика зависит от активного AccessChecker (флаг require_session):

  • Базовый AccessChecker (по умолчанию) — require_session=False:
    dotorm пермиссивен и работает БЕЗ сессии (default-allow). Ставить сессию
    не нужно — CRUD доступен из коробки для автономного использования.

  • Реальный чекер (FARA AccessChecker) — require_session=True:
    политика default-deny. Любая CRUD-операция требует установленной сессии;
    без неё — AccessDenied (защита от забытого Depends / неинициализированного
    контекста). Сессию выставляет каждый вход в ORM:
      - HTTP-запрос: Depends(verify_access) / AnonymousSession для публичных;
      - фон / скрипт / тест: set_access_session(...) (+ clear в конце).

Включить access-control в автономном dotorm:

    set_access_checker(MyChecker())     # свой чекер с require_session=True
    set_access_session(SystemSession()) # готовая сессия полного доступа
    ...
    clear_access_session()

В DotModel вызывается автоматически перед/во время CRUD:
    check_access() → (has_access, domain-фильтр для search).
"""

import functools
import inspect
from contextlib import asynccontextmanager
from contextvars import ContextVar
from enum import StrEnum
from typing import TypeVar, Generic


class Operation(StrEnum):
    """Операции доступа."""

    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


BYPASS_DOMAIN = []
BYPASS_DOMAIN_LEGACY = [["id", "!=", None]]

# Зарезервированный токен для field-level доступа (атрибуты role_* на полях,
# см. fields.Field.required_roles). Означает «писать/читать это поле может
# только суперпользователь». Конкретную трактовку даёт AccessChecker:
# для FARA это session.user_id.is_admin. Это НЕ код реальной роли —
# подобрано так, чтобы не пересекаться с code в таблице roles.
SUPERUSER = "__superuser__"

# Generic тип для Session
TSession = TypeVar("TSession")


# ============================================================
# Built-in access sessions (для автономного использования dotorm)
# ============================================================
#
# Сессия — произвольный объект, который читает ваш AccessChecker (для FARA —
# Session с user_id/ролями из security-модуля). Базовый AccessChecker
# содержимым не интересуется — ему важно лишь, что сессия НЕ None. Эти классы
# дают готовую «осмысленную» сессию, когда вы включаете access-control
# (require_session=True) но не хотите тащить security-модуль FARA.
#
# NB: у FARA есть свои SystemSession/AnonymousSession в
# security.models.sessions — они несут реального пользователя. Эти —
# лёгкие маркеры для standalone.


class SystemSession:
    """Полный доступ — обходит проверки. Для скриптов/миграций/задач/тестов."""

    is_system = True
    user_id = None


class AnonymousSession:
    """Публичная сессия без аутентифицированного пользователя."""

    is_system = False
    user_id = None


class AccessChecker(Generic[TSession]):
    """
    Базовый класс проверки доступа.

    По умолчанию разрешает всё И не требует сессию в контексте
    (require_session=False) — dotorm работает автономно, без access-control.
    Модуль security наследует, переопределяет методы и ставит
    require_session=True, включая политику default-deny.
    """

    # Требовать ли установленную сессию доступа.
    #   False (по умолчанию) — CRUD разрешён даже без сессии в контексте
    #     (пермиссивно / автономное использование dotorm — default-allow).
    #   True — отсутствие сессии трактуется как ошибка → AccessDenied
    #     (default-deny; так делает FARA AccessChecker).
    require_session: bool = False

    def system_session(self):
        """
        Сессия полного доступа — её подставляет .sudo().

        Точка расширения: базовая версия отдаёт маркер dotorm, но проект со
        своей проверкой должен вернуть СВОЮ сессию. FARA, например, сверяет
        полный доступ через isinstance с собственной SystemSession, и чужой
        маркер она бы не признала.
        """
        return SystemSession()

    async def check_access(
        self,
        session: TSession,
        model: str,
        operation: Operation,
        record_ids: list[int] | None = None,
    ) -> tuple[bool, list]:
        """
        Единая проверка доступа: ACL + Rules.

        Args:
            session: Сессия пользователя
            model: Имя модели (таблицы)
            operation: Операция (read/create/update/delete)
            record_ids: ID записей (для проверки Rules)

        Returns:
            (has_access, domain_filter):
            - has_access: True если доступ разрешён
            - domain_filter: фильтр для search (пустой если не нужен)
        """
        return True, []

    async def check_table_access(
        self,
        session: TSession,
        model: str,
        operation: Operation,
    ) -> bool:
        """
        Проверяет доступ к таблице (ACL уровень).
        """
        return True

    async def check_row_access(
        self,
        session: TSession,
        model: str,
        operation: Operation,
        record_ids: list[int],
    ) -> bool:
        """
        Проверяет доступ к записям (Rules уровень).

        Для одной или нескольких записей проверяет что они
        попадают под domain из Rules.
        """
        return True

    async def get_domain_filter(
        self,
        session: TSession,
        model: str,
        operation: Operation,
    ) -> list:
        """
        Возвращает domain-фильтр для ограничения выборки.

        Используется для search — добавляется к filter ДО запроса.
        """
        return []

    async def check_field_access(
        self,
        session: TSession,
        model: str,
        operation: Operation,
        field_names: list[str],
    ) -> list[str]:
        """
        Field-level доступ: какие из переданных полей роль НЕ вправе писать.

        Это третья ось контроля доступа (помимо ACL=таблица и Rules=строка):
        ограничение на уровне отдельных полей записи. Используется против
        privilege escalation через mass-assignment — например, обычный
        пользователь, выставляющий себе role_ids или is_admin.

        Вызывается из write-пути (create/update/update_bulk) уже ПОСЛЕ
        ACL/Rules и только для полей, которые реально меняются и помечены
        атрибутом role_* (фильтрацию «меняется/помечено» делает вызывающий
        слой ORM, у которого есть и payload, и текущее значение).

        Args:
            field_names: поля-кандидаты (уже отобранные как меняющиеся
                и role_*-ограниченные).

        Returns:
            Список полей, запрещённых для записи этой сессией. Пустой —
            всё разрешено. База разрешает всё; политику задаёт security.
        """
        return []


class AccessDenied(Exception):
    """Доступ запрещён."""

    def __init__(self, message: str = "Access denied"):
        self.message = message
        super().__init__(self.message)


# ============================================================
# State
# ============================================================

_state: dict = {"checker": AccessChecker()}

_access_session: ContextVar = ContextVar("access_session", default=None)


# ============================================================
# Public API
# ============================================================


def set_access_checker(checker: "AccessChecker") -> None:
    """Устанавливает AccessChecker (один раз при старте)."""
    _state["checker"] = checker


def get_access_checker() -> "AccessChecker":
    """Возвращает текущий AccessChecker."""
    return _state["checker"]


def set_access_session(session) -> None:
    """Устанавливает сессию для текущего запроса."""
    _access_session.set(session)


def get_access_session():
    """Возвращает сессию текущего запроса."""
    return _access_session.get()


def clear_access_session() -> None:
    """Очищает сессию (после завершения post_init)."""
    _access_session.set(None)


# ============================================================
# sudo: выполнить операцию с полным доступом
# ============================================================


@asynccontextmanager
async def system_access():
    """
    Выполнить блок с полным доступом, вернув прежнюю сессию после выхода.

    Нужен там, где код читает СЛУЖЕБНЫЕ данные в контексте обычного
    пользователя: конфиг, справочник, счётчик. Прикладной код обычно вызывает
    не его, а .sudo() (см. ниже) — так намерение видно прямо в строке вызова.
    """
    token = _access_session.set(get_access_checker().system_session())
    try:
        yield
    finally:
        _access_session.reset(token)


class Sudo:
    """
    Прокси, выполняющий вызовы модели с полным доступом.

        rows = await env.models.system_settings.sudo().get_by_module("turn")
        await record.sudo().update(payload)

    ВАЖНО: любой вызов через прокси возвращает awaitable, даже если сам метод
    синхронный. Права должны действовать ровно на время выполнения, а для
    корутины «время выполнения» наступает только на await — иначе сессия
    вернулась бы обратно раньше, чем метод дошёл бы до запроса.
    """

    __slots__ = ("_target",)

    def __init__(self, target):
        self._target = target

    def __getattr__(self, name):
        attr = getattr(self._target, name)
        if not callable(attr):
            return attr

        @functools.wraps(attr)
        async def with_full_access(*args, **kwargs):
            async with system_access():
                result = attr(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
                return result

        return with_full_access

    def __repr__(self) -> str:
        return f"<Sudo {self._target!r}>"


class SudoAccessor:
    """
    Дескриптор, дающий .sudo() и классу, и записи.

    Обычным методом это не выразить: у класса не к чему привязать self, а
    classmethod потерял бы запись — и record.sudo().update(...) записывал бы
    «в никуда». Дескриптор просто отдаёт то, на чём его позвали.
    """

    def __get__(self, instance, owner):
        target = owner if instance is None else instance
        return lambda: Sudo(target)
