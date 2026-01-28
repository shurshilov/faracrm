"""PostgreSQL transaction management."""

from contextvars import ContextVar

try:
    import asyncpg
    from asyncpg.transaction import Transaction
except ImportError:
    asyncpg = None  # type: ignore
    Transaction = None  # type: ignore

from .session import TransactionSession


# Context variable для хранения текущей сессии транзакции
_current_session: ContextVar["TransactionSession | None"] = ContextVar(
    "current_session", default=None
)


def get_current_session() -> "TransactionSession | None":
    """Получить текущую сессию из контекста (если есть активная транзакция)."""
    return _current_session.get()


class ContainerTransaction:
    """
    Transaction context manager for PostgreSQL.

    Acquires connection, starts transaction, executes queries,
    commits on success, rollbacks on exception.

    Автоматически устанавливает текущую сессию в contextvars,
    так что методы ORM могут использовать её без явной передачи.

    Example:
        async with ContainerTransaction(pool) as session:
            await session.execute("INSERT INTO users ...")
            # Или без явной передачи session:
            await User.create(payload=user)  # session подставится из контекста
            # Commits on exit
    """

    default_pool: "asyncpg.Pool | None" = None

    def __init__(self, pool: "asyncpg.Pool | None" = None):
        self.session_factory = TransactionSession
        if pool is None:
            assert self.default_pool is not None
            self.pool = self.default_pool
        else:
            self.pool = pool
        self._token = None

    async def __aenter__(self):
        connection: "asyncpg.Connection" = await self.pool.acquire()
        transaction = connection.transaction()

        assert isinstance(transaction, Transaction)
        assert isinstance(connection, asyncpg.Connection)

        await transaction.start()
        self.session = self.session_factory(connection, transaction)

        # Устанавливаем текущую сессию в контекст
        self._token = _current_session.set(self.session)

        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Сбрасываем контекст
        if self._token is not None:
            _current_session.reset(self._token)

        if exc_type is not None:
            # Выпало исключение вызвать ролбек
            await self.session.transaction.rollback()
        else:
            # Не выпало исключение вызвать комит
            await self.session.transaction.commit()
        # В любом случае вернуть соединение в пул
        await self.pool.release(self.session.connection)
