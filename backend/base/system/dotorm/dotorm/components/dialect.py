"""
Database dialect definitions.

Centralizes all dialect-specific logic in one place.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Dialect:
    """
    Database dialect configuration.

    Contains all dialect-specific settings:
    - name: dialect identifier
    - escape: character for escaping identifiers ("` for MySQL, " for Postgres)
    - placeholder: parameter placeholder style (%s for MySQL, $N for Postgres)
    - supports_returning: whether INSERT ... RETURNING is supported
    """

    name: Literal["postgres", "mysql", "clickhouse"]
    escape: str
    placeholder: str
    supports_returning: bool

    def escape_identifier(self, identifier: str) -> str:
        """Escape a column/table name."""
        return f"{self.escape}{identifier}{self.escape}"

    def make_placeholders(self, count: int, start: int = 1) -> str:
        """
        Generate placeholder string for given count of parameters.

        For MySQL: %s, %s, %s
        For Postgres: $1, $2, $3
        For Clickhouse: %s, %s, %s
        """
        if self.name == "postgres":
            return ", ".join(f"${i}" for i in range(start, start + count))
        else:
            return ", ".join(["%s"] * count)

    def make_placeholder(self, index: int = 1) -> str:
        """Generate single placeholder."""
        if self.name == "postgres":
            return f"${index}"
        return "%s"

    def get_no_transaction_session(self):
        """Get appropriate session class for this dialect."""
        if self.name == "postgres":
            from ..databases.postgres.session import NoTransactionSession

            return NoTransactionSession
        elif self.name == "mysql":
            from ..databases.mysql.session import NoTransactionSession

            return NoTransactionSession
        else:
            from ..databases.clickhouse.session import NoTransactionSession

            return NoTransactionSession


# Pre-defined dialects
POSTGRES = Dialect(
    name="postgres",
    escape='"',
    placeholder="$",
    supports_returning=True,
)

MYSQL = Dialect(
    name="mysql",
    escape="`",
    placeholder="%s",
    supports_returning=False,
)

CLICKHOUSE = Dialect(
    name="clickhouse",
    escape="`",
    placeholder="%s",
    supports_returning=False,
)


def get_dialect(name: str) -> Dialect:
    """Get dialect by name."""
    if name == "postgres":
        return POSTGRES
    elif name == "mysql":
        return MYSQL
    elif name == "clickhouse":
        return CLICKHOUSE
    else:
        raise ValueError(f"Unknown dialect: {name}")
