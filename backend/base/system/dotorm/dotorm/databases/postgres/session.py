"""PostgreSQL session implementations."""

from typing import Any, Callable, TYPE_CHECKING

from ..abstract.types import PostgresPoolSettings
from ..abstract.session import SessionAbstract
from ..abstract.dialect import PostgresDialect, CursorType


if TYPE_CHECKING:
    import asyncpg
    from asyncpg.transaction import Transaction


# Shared dialect instance
_dialect = PostgresDialect()


class PostgresSession(SessionAbstract):
    """Base PostgreSQL session."""

    @staticmethod
    async def _do_execute(
        conn: "asyncpg.Connection",
        stmt: str,
        values: Any,
        cursor: CursorType,
    ) -> Any:
        """
        Execute query on connection (shared logic).

        Args:
            conn: asyncpg connection
            stmt: SQL with $1, $2... placeholders (already converted)
            values: Query values
            cursor: Cursor type

        Returns:
            Raw result from asyncpg
        """
        # executemany
        if cursor == "executemany":
            if not values:
                raise ValueError("executemany requires values")
            # Handle [[v1, v2], [v3, v4]] or [[[v1, v2], [v3, v4]]] format
            rows = (
                values[0]
                if isinstance(values[0], list)
                and values[0]
                and isinstance(values[0][0], (list, tuple))
                else values
            )
            for row in rows:
                await conn.execute(stmt, *row)
            return None

        # void - execute only (INSERT/UPDATE/DELETE without return)
        if cursor == "void":
            if values:
                await conn.execute(stmt, *values)
            else:
                await conn.execute(stmt)
            return None

        # fetch operations
        method = getattr(conn, _dialect.get_cursor_method(cursor))
        if values:
            return await method(stmt, *values)
        return await method(stmt)


class TransactionSession(PostgresSession):
    """
    Session for transactional queries.
    Uses single connection within transaction context.
    """

    def __init__(
        self, connection: "asyncpg.Connection", transaction: "Transaction"
    ) -> None:
        self.connection = connection
        self.transaction = transaction

    async def execute(
        self,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
        cursor: CursorType = "fetchall",
    ) -> Any:
        stmt = _dialect.convert_placeholders(stmt)
        result = await self._do_execute(self.connection, stmt, values, cursor)

        # Fast path: skip dict() conversion for fetch + prepare
        if prepare and result and cursor in ("fetchall", "fetch"):
            return prepare(result)

        result = _dialect.convert_result(result, cursor)

        if prepare and result:
            return prepare(result)
        return result


class NoTransactionSession(PostgresSession):
    """
    Session for non-transactional queries.
    Acquires connection from pool per query.
    """

    default_pool: "asyncpg.Pool | None" = None

    def __init__(self, pool: "asyncpg.Pool | None" = None) -> None:
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
            result = await self._do_execute(conn, stmt, values, cursor)

            # Fast path: when prepare callback is provided for fetch results,
            # skip dict() conversion — asyncpg Records support ** unpacking,
            # so prepare_list_ids(records) works directly.
            if prepare and result and cursor in ("fetchall", "fetch"):
                return prepare(result)

            result = _dialect.convert_result(result, cursor)

            if prepare and result:
                return prepare(result)
            return result


class NoTransactionNoPoolSession(PostgresSession):
    """
    Session without pool.
    Opens connection, executes, closes. For admin tasks.
    """

    @classmethod
    async def get_connection(
        cls, settings: PostgresPoolSettings
    ) -> "asyncpg.Connection":
        """Create new connection without pool."""
        import asyncpg

        return await asyncpg.connect(**settings.model_dump())

    @classmethod
    async def execute(
        cls,
        settings: PostgresPoolSettings,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
        cursor: str = "execute",
    ) -> Any:
        conn = await cls.get_connection(settings)

        try:
            if values:
                await conn.execute(stmt, values)
            else:
                await conn.execute(stmt)

            rows = await getattr(conn, cursor)()

            if prepare:
                return prepare(rows)
            return rows
        finally:
            await conn.close()
