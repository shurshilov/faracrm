"""Database dialect abstraction (Strategy pattern)."""

from abc import ABC, abstractmethod
from typing import Any, Literal


# Unified cursor types for all dialects
CursorType = Literal[
    "fetchall",
    "fetch",
    "fetchrow",
    "fetchval",
    "executemany",
    "lastrowid",  # MySQL-specific
    "void",  # Execute without returning results
]


class Dialect(ABC):
    """
    Abstract dialect defining database-specific behavior.

    Each database has its own dialect that handles:
    - Placeholder conversion (%s → $1 for Postgres, %s stays for MySQL)
    - Cursor method mapping (fetchall → fetch for asyncpg)
    - Result conversion (Record → dict)
    """

    _cursor_map: dict[str, str]

    def convert_placeholders(self, stmt: str) -> str:
        """Convert %s placeholders to database-specific format."""
        return stmt

    def get_cursor_method(self, cursor: CursorType) -> str:
        """Map CursorType to actual driver method name."""
        return self._cursor_map.get(cursor, "void")

    @abstractmethod
    def convert_result(self, rows: Any, cursor: CursorType) -> Any:
        """Convert raw database result to standard format (list of dicts, etc)."""
        ...


class PostgresDialect(Dialect):
    """PostgreSQL dialect for asyncpg driver."""

    _cursor_map = {
        "fetchall": "fetch",
        "fetch": "fetch",
        "fetchrow": "fetchrow",
        "fetchval": "fetchval",
    }

    def convert_placeholders(self, stmt: str) -> str:
        """Convert %s to $1, $2, $3... in a single pass."""
        if "%s" not in stmt:
            return stmt
        parts = stmt.split("%s")
        result = [parts[0]]
        for i, part in enumerate(parts[1:], 1):
            result.append(f"${i}")
            result.append(part)
        return "".join(result)

    def convert_result(self, rows: Any, cursor: CursorType) -> Any:
        """Convert asyncpg Record objects to dicts."""
        if rows is None or cursor in ("void", "executemany"):
            return rows

        if cursor == "fetchval":
            return rows  # Single value

        if cursor == "fetchrow":
            return dict(rows) if rows else None

        # fetchall/fetch
        return [dict(rec) for rec in rows] if rows else []


class MySQLDialect(Dialect):
    """MySQL dialect for aiomysql driver."""

    _cursor_map = {
        "fetchall": "fetchall",
        "fetch": "fetchall",
        "fetchrow": "fetchone",
        "fetchval": "fetchone",
    }

    def convert_result(self, rows: Any, cursor: CursorType) -> Any:
        """Convert MySQL results."""
        if rows is None or cursor in ("void", "executemany", "lastrowid"):
            return rows

        if cursor == "fetchval":
            # fetchone returns tuple, get first element
            return (
                rows[0] if rows and isinstance(rows, (tuple, list)) else rows
            )

        if cursor == "fetchrow":
            return dict(rows) if rows else None

        # fetchall/fetch
        return [dict(rec) for rec in rows] if rows else []


class ClickHouseDialect(Dialect):
    """ClickHouse dialect for asynch driver."""

    _cursor_map = {
        "fetchall": "fetchall",
        "fetch": "fetchall",
        "fetchrow": "fetchone",
        "fetchval": "fetchone",
    }

    def convert_result(self, rows: Any, cursor: CursorType) -> Any:
        """Convert ClickHouse results to dicts."""
        if rows is None or cursor in ("void", "executemany"):
            return rows

        if cursor == "fetchval":
            # fetchone returns tuple, get first element
            if rows and isinstance(rows, (tuple, list)):
                return rows[0]
            return rows

        if cursor == "fetchrow":
            # Single row - convert to dict if tuple with column info
            return dict(rows) if rows and hasattr(rows, "_fields") else rows

        # fetchall/fetch - list of tuples
        if rows and hasattr(rows[0], "_fields"):
            return [dict(rec._asdict()) for rec in rows]
        return rows if rows else []
