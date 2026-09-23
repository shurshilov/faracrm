"""Access control mixin for DotModel."""

from typing import TYPE_CHECKING

from ...access import (
    get_access_checker,
    get_access_session,
    AccessDenied,
    Operation,
    SudoAccessor,
)

if TYPE_CHECKING:
    from ..protocol import DotModelProtocol

    _Base = DotModelProtocol
else:
    _Base = object


def _filter_field_names(expr) -> set[str]:
    """Имена полей из триплетов фильтра — так же, как их видит FilterParser."""
    names: set[str] = set()
    if isinstance(expr, (list, tuple)):
        if len(expr) == 3 and isinstance(expr[0], str):
            names.add(expr[0])
        else:
            for item in expr:
                names |= _filter_field_names(item)
    return names


class AccessMixin(_Base):
    """
    Mixin добавляющий проверку доступа в CRUD операции.

    Политика зависит от активного чекера (AccessChecker.require_session):
      • require_session=False (базовый пермиссивный чекер, по умолчанию) —
        default-allow: без сессии CRUD разрешён (автономный dotorm).
      • require_session=True (FARA SecurityAccessChecker) — default-deny: без
        сессии в контексте операция запрещается с AccessDenied (защита от
        забытого Depends / неинициализированного контекста). Публичные роуты
        ставят AnonymousSession, фон/тесты — свою через set_access_session.
    SystemSession даёт полный доступ.
    """

    # Выполнить операцию с полным доступом — как .sudo() в Odoo:
    #     await env.models.system_settings.sudo().get_by_module("turn")
    #     await record.sudo().update(payload)
    # Работает и от класса, и от записи (см. SudoAccessor). Права держатся
    # ровно на время вызова и снимаются даже при исключении.
    sudo = SudoAccessor()

    @classmethod
    async def _check_access(
        cls,
        operation: Operation,
        record_ids: list[int] | None = None,
        filter: list | None = None,
    ) -> list | None:
        """
        Raises:
            AccessDenied: если сессия не установлена либо доступ запрещён
        """
        session = get_access_session()
        checker = get_access_checker()
        if session is None:
            # Политика зависит от чекера:
            #   require_session=True (реальный security-чекер) → default-deny:
            #     нет сессии = явная ошибка конфигурации (забытый Depends /
            #     неинициализированный контекст фоновой задачи).
            #   require_session=False (базовый пермиссивный / автономный
            #     dotorm) → default-allow: пускаем без проверок.
            if checker.require_session:
                raise AccessDenied(
                    f"No session in DotORM context for {operation.value} on "
                    f"{cls.__table__}. Public routes must set AnonymousSession "
                    f"explicitly via Depends(AuthTokenApp.use_anonymous_session)."
                )
            return filter

        has_access, domain = await checker.check_access(
            session, cls.__table__, operation, record_ids
        )

        if not has_access:
            raise AccessDenied(
                f"No {operation.value} access to {cls.__table__}"
            )

        if domain:
            if filter:
                # Объединяем filter и domain через AND.
                # Domain оборачивается в вложенный list, чтобы FilterParser
                # обработал его как одно выражение и обернул в скобки.
                # Иначе при наличии OR в domain получается некорректный SQL:
                #   filter AND a OR b  →  (filter AND a) OR b  (неправильно!)
                # А нам нужно:
                #   filter AND (a OR b)
                # При вложенном list парсер ставит скобки автоматически
                # (см. wrap=True в FilterParser._is_triplet)
                return [*filter, domain]
            return domain

        return filter

    # =========================================================================
    # Field-level access (третья ось: ACL=таблица, Rules=строка, тут=поле)
    # =========================================================================

    @classmethod
    async def _check_field_access(
        cls,
        operation: Operation,
        fields,
        filter: list | None = None,
        sort: str | None = None,
    ) -> list[str]:
        """Field-level доступ (атрибуты role_*). Какие поля сессии запрещены,
        решает чекер; здесь — что с ними делать.

        Запись (CREATE/UPDATE): запрещённое поле в payload — AccessDenied,
        операция отклоняется целиком. Защита от privilege escalation через
        mass-assignment: например, обычный пользователь, выставляющий себе
        role_ids или is_admin. Presence-based (как Odoo groups=): проверяется
        любое присутствие поля. КОНТРАКТ: фронт НЕ шлёт restricted-поле юзеру,
        который его не меняет (форма отправляет только изменённые поля).

        Чтение (READ): запрещённые поля вырезаются, как будто их нет, —
        запрос проходит, из базы они не читаются. Фильтр и сортировка по
        ним — ошибка, как по неизвестному полю: иначе значение подбиралось
        бы посимвольно.

        Без сессии ничего не проверяем: _check_access (на записи — до, на
        чтении — сразу после) откажет сам при require_session, иначе доступ
        открыт (автономный dotorm).

        Args:
            operation: READ, CREATE или UPDATE.
            fields: на записи — назначенные поля, на чтении — выбираемые.
            filter, sort: только чтение — что клиент прислал в запросе.

        Returns:
            Поля, которые остаются (на записи — fields как есть).

        Raises:
            AccessDenied: запись запрещённого поля.
            ValueError: фильтр или сортировка по запрещённому для чтения полю.
        """
        session = get_access_session()
        if session is None:
            return list(fields)

        used = _filter_field_names(filter)
        if sort:
            used.add(sort)
        denied = set(
            await get_access_checker().check_field_access(
                session, cls.__table__, operation, [*fields, *used]
            )
        )
        if operation != Operation.READ:
            if denied:
                raise AccessDenied(
                    f"No permission to set field(s) {sorted(denied)} "
                    f"on {cls.__table__}"
                )
            return list(fields)
        if denied & used:
            raise ValueError(
                f"Unknown or private filter field: {sorted(denied & used)!r}"
            )
        return [name for name in fields if name not in denied]
