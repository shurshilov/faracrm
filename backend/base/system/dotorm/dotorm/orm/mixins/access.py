"""Access control mixin for DotModel."""

from typing import TYPE_CHECKING

from ...access import (
    get_access_checker,
    get_access_session,
    AccessDenied,
    Operation,
)

if TYPE_CHECKING:
    from ..protocol import DotModelProtocol

    _Base = DotModelProtocol
else:
    _Base = object


class AccessMixin(_Base):
    """
    Mixin добавляющий проверку доступа в CRUD операции.

    Если AccessSession не установлена — проверки пропускаются.
    SystemSession даёт полный доступ.
    """

    @classmethod
    async def _check_access(
        cls,
        operation: Operation,
        record_ids: list[int] | None = None,
        filter: list | None = None,
    ) -> list | None:
        """
        Единый метод проверки доступа.

        Args:
            operation: Operation.READ / CREATE / UPDATE / DELETE
            record_ids: ID записей (для get/update/delete)
            filter: пользовательский фильтр (для search)

        Returns:
            Модифицированный filter с domain (для search)

        Raises:
            AccessDenied: если доступ запрещён
        """
        session = get_access_session()
        if session is None:
            return filter

        checker = get_access_checker()

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
