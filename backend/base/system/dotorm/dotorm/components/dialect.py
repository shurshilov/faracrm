"""
Database dialect definitions (Strategy pattern, builder layer).

"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..fields import Field


class Dialect(ABC):
    """
    Abstract builder-layer dialect (Strategy).

    Concrete subclasses declare four config attributes as class attributes:
    - name: dialect identifier
    - escape: character for escaping identifiers ('"' for Postgres, '`' for MySQL)
    - placeholder: parameter placeholder style ('$' for Postgres, '%s' otherwise)
    - supports_returning: whether INSERT ... RETURNING is supported

    ...and implement the dialect-specific fragment builders below.
    """

    # Config — provided by concrete subclasses as class attributes.
    name: Literal["postgres", "mysql", "clickhouse"]
    escape: str
    placeholder: str
    supports_returning: bool

    # --- equality / hashing (preserved from the former frozen dataclass) ---
    # Dialects are singletons discriminated by name; keep value-equality so
    # `cls._dialect == POSTGRES` and dict/set usage behave as before.
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Dialect) and other.name == self.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"

    # --- identifier / placeholder helpers ---
    def escape_identifier(self, identifier: str) -> str:
        """Escape a column/table name."""
        return f"{self.escape}{identifier}{self.escape}"

    @abstractmethod
    def make_placeholders(self, count: int, start: int = 1) -> str:
        """Generate a comma-separated placeholder string for `count` params."""
        ...

    @abstractmethod
    def make_placeholder(self, index: int = 1) -> str:
        """Generate a single placeholder."""
        ...

    # --- bulk id-set matching (shared by bulk DELETE and bulk UPDATE) ---
    @abstractmethod
    def make_ids_predicate(self, count: int, ids_first: bool = False) -> str:
        """SQL fragment matching a set of `count` ids, e.g. ``id = ANY($1::int[])``
        (Postgres) or ``id IN (%s, %s, %s)`` (MySQL).

        ids_first=True means the id param is the only/leading bind param (bulk
        DELETE) — Postgres emits the literal ``$1``. ids_first=False means it
        trails other params (bulk UPDATE, after the SET values) — Postgres emits
        ``%s`` and lets the driver number it."""
        ...

    @abstractmethod
    def bind_ids(self, ids: list[int]) -> list:
        """Shape id values to match make_ids_predicate: a single array param
        for Postgres, individual scalars for MySQL."""
        ...

    # --- bulk insert source clause (tail after ``INSERT INTO t (cols)``) ---
    @abstractmethod
    def make_bulk_insert_source(
        self,
        payloads_dicts: list[dict[str, Any]],
        fields_list: list[str],
        fields: "dict[str, Field]",
    ) -> tuple[str, list]:
        """Build the clause following ``INSERT INTO table (columns)`` plus its
        params: ``SELECT * FROM unnest(...)`` (Postgres) or ``VALUES (...), ...``
        (MySQL). payloads_dicts is guaranteed non-empty."""
        ...

    # --- bulk UPDATE with per-row values (single statement) ---
    def make_bulk_update_rows(
        self,
        rows: list[dict[str, Any]],
        fields_list: list[str],
        fields: "dict[str, Field]",
    ) -> tuple[str, str, list] | None:
        """(set_clause, from_clause, params) for ``UPDATE t SET ... FROM ...
        WHERE t.id = v.id`` writing DIFFERENT values per row in one statement.
        None when the dialect has no single-statement form — the caller falls
        back to one UPDATE per row. rows share the same keys, "id" included."""
        return None

    @abstractmethod
    def get_no_transaction_session(self):
        """Return the driver session class (no-transaction) for this dialect."""
        ...


# Mapping of SQL types to PostgreSQL array cast types for unnest().
# Postgres-only concern — lives with the Postgres dialect that uses it.
_PG_ARRAY_TYPE_MAP = {
    "INTEGER": "int4",
    "SERIAL": "int4",
    "BIGINT": "int8",
    "BIGSERIAL": "int8",
    "SMALLINT": "int2",
    "SMALLSERIAL": "int2",
    "TEXT": "text",
    "BOOL": "bool",
    "TIMESTAMPTZ": "timestamptz",
    "DATE": "date",
    "TIME": "time",
    "TIMETZ": "timetz",
    "DOUBLE PRECISION": "float8",
    "JSONB": "jsonb",
    "JSON": "jsonb",
}


class PostgresSqlDialect(Dialect):
    """PostgreSQL: numbered placeholders + array-param bulk ops."""

    name = "postgres"
    escape = '"'
    placeholder = "$"
    supports_returning = True

    def make_placeholders(self, count: int, start: int = 1) -> str:
        return ", ".join(f"${i}" for i in range(start, start + count))

    def make_placeholder(self, index: int = 1) -> str:
        return f"${index}"

    def make_ids_predicate(self, count: int, ids_first: bool = False) -> str:
        # Single array param, no per-id parse overhead. When ids is the only/
        # leading param (DELETE) use the literal $1; when it trails the SET
        # params (UPDATE) use %s and let the driver number it as $N.
        placeholder = "$1" if ids_first else "%s"
        return f"id = ANY({placeholder}::int[])"

    def bind_ids(self, ids: list[int]) -> list:
        # one array parameter
        return [ids]

    def _array_cast_type(self, sql_type: str) -> str:
        """Map a column SQL type to its PostgreSQL array cast type for unnest()."""
        upper = sql_type.upper()
        if upper in _PG_ARRAY_TYPE_MAP:
            return _PG_ARRAY_TYPE_MAP[upper]
        # VARCHAR(N) -> text
        if upper.startswith("VARCHAR"):
            return "text"
        # DECIMAL(M,N) -> numeric
        if upper.startswith("DECIMAL"):
            return "numeric"
        # Fallback
        return "text"

    def make_bulk_insert_source(
        self,
        payloads_dicts: list[dict[str, Any]],
        fields_list: list[str],
        fields: "dict[str, Field]",
    ) -> tuple[str, list]:
        """unnest approach — one array param per column.

        ... SELECT * FROM unnest($1::text[], $2::int4[], $3::bool[])
        For 5000 rows × 10 fields = 10 params instead of 50,000.
        """
        # Build column arrays (transpose rows→columns)
        column_arrays = []
        unnest_params = []
        for i, field_name in enumerate(fields_list, 1):
            col_values = [row[field_name] for row in payloads_dicts]
            column_arrays.append(col_values)

            # Get PostgreSQL array type from field definition
            field_obj = fields.get(field_name)
            if field_obj:
                # sql_type can be class attr (str) or property
                pg_type = self._array_cast_type(field_obj.sql_type)
            else:
                pg_type = "text"
            unnest_params.append(f"${i}::{pg_type}[]")

        unnest_clause = ", ".join(unnest_params)
        return f"SELECT * FROM unnest({unnest_clause})", column_arrays

    def make_bulk_update_rows(
        self,
        rows: list[dict[str, Any]],
        fields_list: list[str],
        fields: "dict[str, Field]",
    ) -> tuple[str, str, list]:
        """Разные значения на строку одним UPDATE через unnest:

            UPDATE t SET "f" = v."f", ...
            FROM unnest($1::int4[], $2::numeric[], ...) AS v("id", "f", ...)
            WHERE t.id = v.id

        По массиву на колонку (первый — id), как в make_bulk_insert_source.
        """
        columns = ["id", *fields_list]
        arrays: list = []
        casts: list[str] = []
        for i, name in enumerate(columns, 1):
            arrays.append([row.get(name) for row in rows])
            field_obj = fields.get(name)
            pg_type = (
                self._array_cast_type(field_obj.sql_type)
                if field_obj
                else "text"
            )
            casts.append(f"${i}::{pg_type}[]")
        set_clause = ", ".join(
            f"{self.escape_identifier(f)} = v.{self.escape_identifier(f)}"
            for f in fields_list
        )
        from_clause = (
            f"FROM unnest({', '.join(casts)}) "
            f"AS v({', '.join(self.escape_identifier(c) for c in columns)})"
        )
        return set_clause, from_clause, arrays

    def get_no_transaction_session(self):
        from ..databases.postgres.session import NoTransactionSession

        return NoTransactionSession


class _DefaultSqlDialect(Dialect):
    """
    Shared SQL-string shapes for %s-placeholder databases (MySQL, ClickHouse).

    These engines lack Postgres array params, so bulk ops expand to individual
    placeholders. Concrete subclasses set `name`, `escape` and the driver
    session; everything else is shared here.
    """

    placeholder = "%s"
    supports_returning = False

    def make_placeholders(self, count: int, start: int = 1) -> str:
        return ", ".join(["%s"] * count)

    def make_placeholder(self, index: int = 1) -> str:
        return "%s"

    def make_ids_predicate(self, count: int, ids_first: bool = False) -> str:
        # MySQL/CH: individual placeholders regardless of position.
        return f"id IN ({self.make_placeholders(count)})"

    def bind_ids(self, ids: list[int]) -> list:
        # individual scalar params
        return list(ids)

    def make_bulk_insert_source(
        self,
        payloads_dicts: list[dict[str, Any]],
        fields_list: list[str],
        fields: "dict[str, Field]",
    ) -> tuple[str, list]:
        """... VALUES (%s,%s,...), (%s,%s,...), ..."""
        num_fields = len(fields_list)

        all_values: list = []
        value_groups = []
        placeholder_group = f"({self.make_placeholders(num_fields)})"

        for payload_dict in payloads_dicts:
            for field in fields_list:
                all_values.append(payload_dict[field])
            value_groups.append(placeholder_group)

        values_clause = ", ".join(value_groups)
        return f"VALUES {values_clause}", all_values


class MysqlSqlDialect(_DefaultSqlDialect):
    """MySQL dialect."""

    name = "mysql"
    escape = "`"

    def get_no_transaction_session(self):
        from ..databases.mysql.session import NoTransactionSession

        return NoTransactionSession


class ClickhouseSqlDialect(_DefaultSqlDialect):
    """ClickHouse dialect — same SQL-string shapes as MySQL, distinct driver session."""

    name = "clickhouse"
    escape = "`"

    def get_no_transaction_session(self):
        from ..databases.clickhouse.session import NoTransactionSession

        return NoTransactionSession


# Pre-defined dialect singletons (kept as module-level instances for import
# compatibility: `from dotorm.components import POSTGRES`, `== POSTGRES`, etc.)
POSTGRES = PostgresSqlDialect()
MYSQL = MysqlSqlDialect()
CLICKHOUSE = ClickhouseSqlDialect()


def get_dialect(name: str) -> Dialect:
    """Get dialect singleton by name."""
    if name == "postgres":
        return POSTGRES
    elif name == "mysql":
        return MYSQL
    elif name == "clickhouse":
        return CLICKHOUSE
    else:
        raise ValueError(f"Unknown dialect: {name}")
