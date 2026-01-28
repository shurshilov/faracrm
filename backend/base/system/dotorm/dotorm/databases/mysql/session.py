"""MySQL session implementations."""

from typing import Any, Callable, TYPE_CHECKING

from ..abstract.session import SessionAbstract
from ..abstract.dialect import MySQLDialect, CursorType


if TYPE_CHECKING:
    import aiomysql


# Shared dialect instance
_dialect = MySQLDialect()


class MysqlSession(SessionAbstract):
    """Base MySQL session."""

    @staticmethod
    async def _do_execute(
        cursor: "aiomysql.Cursor",
        stmt: str,
        values: Any,
        cursor_type: CursorType,
    ) -> Any:
        """
        Execute query on cursor (shared logic).

        Args:
            cursor: aiomysql cursor
            stmt: SQL with %s placeholders
            values: Query values
            cursor_type: Cursor type

        Returns:
            Raw result from aiomysql
        """
        # executemany
        if cursor_type == "executemany":
            if not values:
                raise ValueError("executemany requires values")
            await cursor.executemany(stmt, values)
            return None

        # Execute query
        if values:
            await cursor.execute(stmt, values)
        else:
            await cursor.execute(stmt)

        # void - execute only (INSERT/UPDATE/DELETE without return)
        if cursor_type == "void":
            return None

        # lastrowid special case
        if cursor_type == "lastrowid":
            return cursor.lastrowid

        # fetch operations
        method = getattr(cursor, _dialect.get_cursor_method(cursor_type))
        return await method()


class TransactionSession(MysqlSession):
    """
    Session for transactional queries.
    Uses single connection within transaction context.
    """

    def __init__(
        self, connection: "aiomysql.Connection", cursor: "aiomysql.Cursor"
    ) -> None:
        self.connection = connection
        self.cursor = cursor

    async def execute(
        self,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
        cursor: CursorType = "fetchall",
    ) -> Any:
        stmt = _dialect.convert_placeholders(stmt)
        result = await self._do_execute(self.cursor, stmt, values, cursor)
        result = _dialect.convert_result(result, cursor)

        if prepare and result:
            return prepare(result)
        return result


class NoTransactionSession(MysqlSession):
    """
    Session for non-transactional queries.
    Acquires connection from pool per query.
    """

    default_pool: "aiomysql.Pool | None" = None

    def __init__(self, pool: "aiomysql.Pool | None" = None) -> None:
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
        import aiomysql
        
        stmt = _dialect.convert_placeholders(stmt)

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                result = await self._do_execute(cur, stmt, values, cursor)
                result = _dialect.convert_result(result, cursor)

                if prepare and result:
                    return prepare(result)
                return result
