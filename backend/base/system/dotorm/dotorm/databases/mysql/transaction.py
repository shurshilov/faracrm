"""MySQL transaction management."""

try:
    import aiomysql
except ImportError:
    aiomysql = None  # type: ignore

from .session import TransactionSession


class ContainerTransaction:
    """
    Transaction context manager for MySQL.

    Acquires connection, executes queries,
    commits on success, rollbacks on exception.
    """

    def __init__(self, pool: "aiomysql.Pool"):
        self.pool = pool

    async def __aenter__(self):
        connection: "aiomysql.Connection" = await self.pool.acquire()
        cursor: "aiomysql.Cursor" = await connection.cursor(
            aiomysql.DictCursor
        )
        self.session = TransactionSession(connection, cursor)
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Выпало исключение вызвать ролбек
            await self.session.connection.rollback()
        else:
            # Не выпало исключение вызвать комит
            await self.session.connection.commit()
        await self.session.cursor.close()
        # В любом случае закрыть соединение и курсор
        self.pool.release(self.session.connection)
