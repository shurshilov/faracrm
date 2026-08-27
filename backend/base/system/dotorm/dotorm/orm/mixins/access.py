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
        payload,
        fields,
    ) -> None:
        """Проверяет право записи отдельных полей (role_*).

        Защита от privilege escalation через mass-assignment: например,
        обычный пользователь, выставляющий себе role_ids или is_admin.

        Presence-based (как Odoo groups=): любое присутствие role_*-поля
        в payload проверяется у checker'а.

        КОНТРАКТ: фронт НЕ должен слать restricted-поле юзеру, который его
        не меняет — иначе его легитимная правка будет отклонена целиком.
        Т.к. форма сейчас шлёт is_admin при каждом сохранении, для
        не-суперпользователя это поле надо скрывать/не отправлять
        (UI-reflection).

        Вызывается из write-пути ПОСЛЕ _check_access (ACL+Rules).

        Args:
            operation: CREATE или UPDATE (READ проверяется при выборке).
            payload: модель с новыми значениями.
            fields: имена назначенных полей.

        Raises:
            AccessDenied: если хотя бы одно поле запрещено для записи.
        """
        all_fields = cls.get_fields()
        to_check: list[str] = []
        for name in fields:
            field = all_fields.get(name)
            if field is not None and field.required_roles(operation.value):
                to_check.append(name)

        if not to_check:
            return

        session = get_access_session()
        checker = get_access_checker()
        if session is None:
            # Как и в _check_access: жёстко только при require_session=True.
            if checker.require_session:
                raise AccessDenied(
                    f"No session in DotORM context for field-level "
                    f"{operation.value} on {cls.__table__}."
                )
            return

        denied = await checker.check_field_access(
            session, cls.__table__, operation, to_check
        )
        if denied:
            raise AccessDenied(
                f"No permission to set field(s) {denied} "
                f"on {cls.__table__}"
            )
