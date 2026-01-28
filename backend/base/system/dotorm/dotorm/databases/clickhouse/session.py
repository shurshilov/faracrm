"""ClickHouse session implementations."""

from typing import Any, Callable, TYPE_CHECKING

from ..abstract.session import SessionAbstract
from ..abstract.dialect import ClickHouseDialect, CursorType


if TYPE_CHECKING:
    import asynch
    from asynch.cursors import Cursor


# Shared dialect instance
_dialect = ClickHouseDialect()


class ClickhouseSession(SessionAbstract):
    """Base ClickHouse session."""

    @staticmethod
    async def _do_execute(
        cursor: "Cursor",
        stmt: str,
        values: Any,
        cursor_type: CursorType,
    ) -> Any:
        """
        Execute query on cursor (shared logic).

        Args:
            cursor: asynch cursor
            stmt: SQL with %s placeholders
            values: Query values
            cursor_type: Cursor type

        Returns:
            Raw result from asynch
        """
        # executemany
        if cursor_type == "executemany":
            if not values:
                raise ValueError("executemany requires values")
            for row in values:
                await cursor.execute(stmt, row)
            return None

        # Execute query
        if values:
            await cursor.execute(stmt, values)
        else:
            await cursor.execute(stmt)

        # void - execute only (INSERT without return)
        if cursor_type == "void":
            return None

        # fetch operations
        method_name = _dialect.get_cursor_method(cursor_type)
        if method_name:
            method = getattr(cursor, method_name)
            return await method()
        return None


class NoTransactionSession(ClickhouseSession):
    """
    Session for non-transactional queries.
    Acquires connection from pool per query.

    Note: ClickHouse doesn't support transactions.
    """

    default_pool: "asynch.Pool | None" = None

    def __init__(self, pool: "asynch.Pool | None" = None) -> None:
        if pool is None:
            assert self.default_pool is not None
            self.pool = self.default_pool
        else:
            self.pool = pool

    async def execute(
        self,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
        cursor: CursorType = "fetchall",
    ) -> Any:
        stmt = _dialect.convert_placeholders(stmt)

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                result = await self._do_execute(cur, stmt, values, cursor)
                result = _dialect.convert_result(result, cursor)

                if prepare and result:
                    return prepare(result)
                return result
