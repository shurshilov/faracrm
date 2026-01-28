"""Abstract session interface."""

from abc import ABC, abstractmethod
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .dialect import CursorType


class SessionAbstract(ABC):
    """
    Abstract database session.

    Subclasses must implement execute() method.
    Use dialect helper for SQL transformations.
    """

    @abstractmethod
    async def execute(
        self,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
        cursor: "CursorType" = "fetchall",
    ) -> Any:
        """
        Execute SQL query.

        Args:
            stmt: SQL statement with %s placeholders
            values: Query parameters:
                - Tuple/list for single query
                - List of tuples for executemany
            prepare: Optional function to transform results
            cursor: Fetch mode:
                - "fetchall"/"fetch": Return list of dicts
                - "fetchrow": Return single dict or None
                - "fetchval": Return single value or None
                - "executemany": Execute multiple inserts
                - "lastrowid": Return last inserted row ID (MySQL only)
                - "void": Execute without returning rows (INSERT/UPDATE/DELETE)

        Returns:
            Query results based on cursor mode

        Example:
            # Fetch all rows
            rows = await session.execute("SELECT * FROM users WHERE active = %s", (True,))

            # Fetch single row
            user = await session.execute("SELECT * FROM users WHERE id = %s", (1,), cursor="fetchrow")

            # Fetch single value
            count = await session.execute("SELECT COUNT(*) FROM users", cursor="fetchval")

            # Execute without return
            await session.execute("UPDATE users SET active = %s", (False,), cursor="void")

            # Execute many
            await session.execute(
                "INSERT INTO users (name) VALUES (%s)",
                [("Alice",), ("Bob",)],
                cursor="executemany"
            )
        """
        ...
