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

    # --- LIKE patterns ---
    # Escape-символ LIKE по умолчанию: «\» у Postgres, MySQL и ClickHouse,
    # поэтому реализация общая; диалект с другим правилом переопределяет
    # атрибут (или метод целиком).
    like_escape_char: str = "\\"

    def like_escape(self, text: str) -> str:
        """Экранировать пользовательский текст для подстановки в LIKE/ILIKE.

        `%` и `_` в шаблоне — подстановочные знаки, а хвостовой escape-символ
        ломает запрос («LIKE pattern must not end with escape character»).
        Сам шаблон (`%…%`) добавляет вызывающий. Единственная точка для всех
        поисков по подстроке — роутеры/модели свои replace не пишут.
        """
        esc = self.like_escape_char
        return (
            text.replace(esc, esc + esc)
            .replace("%", esc + "%")
            .replace("_", esc + "_")
        )

    # Единственный язык плейсхолдеров в SQL-тексте — ``%s`` (как у DB-API):
    # так пишут и билдер, и сырой SQL приложения. В ``$1, $2…`` для asyncpg
    # его переводит один адаптер на границе драйвера (Postgres-сессия);
    # литералов ``$n`` в тексте запросов нет.
    @abstractmethod
    def make_placeholders(self, count: int) -> str:
        """Generate a comma-separated placeholder string for `count` params."""
        ...

    # --- bulk id-set matching (shared by bulk DELETE and bulk UPDATE) ---
    @abstractmethod
    def make_ids_predicate(self, count: int) -> str:
        """SQL fragment matching a set of `count` ids: ``id = ANY(%s::int[])``
        (Postgres, one array param) or ``id IN (%s, %s, %s)`` (MySQL)."""
        ...

    @abstractmethod
    def bind_ids(self, ids: list[int]) -> list:
        """Shape id values to match make_ids_predicate: a single array param
        for Postgres, individual scalars for MySQL."""
        ...

    # --- IN / NOT IN of a filter triplet ---
    @abstractmethod
    def make_in_predicate(
        self, field: str, op: str, values: list | tuple
    ) -> tuple[str, tuple]:
        """``field IN (...)`` / ``field NOT IN (...)`` with its bind params.

        Postgres: one array param (``= ANY`` / ``<> ALL``) — the SQL text
        does not depend on the list length (prepared statement cache) and
        the 32767-parameter limit does not apply. MySQL: N placeholders.
        Empty list: IN → FALSE, NOT IN → TRUE (``IN ()`` is invalid SQL)."""
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

    # --- m2m links: all id pairs in one INSERT ---
    @abstractmethod
    def make_link_pairs_source(
        self, pairs: list[tuple[int, int]]
    ) -> tuple[str, list]:
        """Хвост после ``INSERT INTO link_table (col_a, col_b)`` для пар id
        и его параметры: ``SELECT * FROM unnest(%s::int[], %s::int[])``
        (Postgres, два массива) или ``VALUES (%s, %s), (%s, %s), ...``
        (MySQL). Один запрос на всю пачку. pairs непустой."""
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

    def make_placeholders(self, count: int) -> str:
        return ", ".join(["%s"] * count)

    def make_ids_predicate(self, count: int) -> str:
        # Single array param, no per-id parse overhead.
        return "id = ANY(%s::int[])"

    def bind_ids(self, ids: list[int]) -> list:
        # one array parameter
        return [ids]

    def make_in_predicate(
        self, field: str, op: str, values: list | tuple
    ) -> tuple[str, tuple]:
        if not values:
            return ("FALSE" if op == "in" else "TRUE"), ()
        compare = "= ANY(%s)" if op == "in" else "<> ALL(%s)"
        return f"{field} {compare}", (list(values),)

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

        ... SELECT * FROM unnest(%s::text[], %s::int4[], %s::bool[])
        For 5000 rows × 10 fields = 10 params instead of 50,000.
        """
        # Build column arrays (transpose rows→columns)
        column_arrays = []
        unnest_params = []
        for field_name in fields_list:
            col_values = [row[field_name] for row in payloads_dicts]
            column_arrays.append(col_values)

            # Get PostgreSQL array type from field definition
            field_obj = fields.get(field_name)
            if field_obj:
                # sql_type can be class attr (str) or property
                pg_type = self._array_cast_type(field_obj.sql_type)
            else:
                pg_type = "text"
            unnest_params.append(f"%s::{pg_type}[]")

        unnest_clause = ", ".join(unnest_params)
        return f"SELECT * FROM unnest({unnest_clause})", column_arrays

    def make_link_pairs_source(
        self, pairs: list[tuple[int, int]]
    ) -> tuple[str, list]:
        first = [pair[0] for pair in pairs]
        second = [pair[1] for pair in pairs]
        return "SELECT * FROM unnest(%s::int[], %s::int[])", [first, second]

    def make_bulk_update_rows(
        self,
        rows: list[dict[str, Any]],
        fields_list: list[str],
        fields: "dict[str, Field]",
    ) -> tuple[str, str, list]:
        """Разные значения на строку одним UPDATE через unnest:

            UPDATE t SET "f" = v."f", ...
            FROM unnest(%s::int4[], %s::numeric[], ...) AS v("id", "f", ...)
            WHERE t.id = v.id

        По массиву на колонку (первый — id), как в make_bulk_insert_source.
        """
        columns = ["id", *fields_list]
        arrays: list = []
        casts: list[str] = []
        for name in columns:
            arrays.append([row.get(name) for row in rows])
            field_obj = fields.get(name)
            pg_type = (
                self._array_cast_type(field_obj.sql_type)
                if field_obj
                else "text"
            )
            casts.append(f"%s::{pg_type}[]")
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

    def make_placeholders(self, count: int) -> str:
        return ", ".join(["%s"] * count)

    def make_ids_predicate(self, count: int) -> str:
        # MySQL/CH: individual placeholders.
        return f"id IN ({self.make_placeholders(count)})"

    def bind_ids(self, ids: list[int]) -> list:
        # individual scalar params
        return list(ids)

    def make_in_predicate(
        self, field: str, op: str, values: list | tuple
    ) -> tuple[str, tuple]:
        if not values:
            return ("FALSE" if op == "in" else "TRUE"), ()
        placeholders = self.make_placeholders(len(values))
        return f"{field} {op.upper()} ({placeholders})", tuple(values)

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

    def make_link_pairs_source(
        self, pairs: list[tuple[int, int]]
    ) -> tuple[str, list]:
        groups = ", ".join(["(%s, %s)"] * len(pairs))
        return f"VALUES {groups}", [value for pair in pairs for value in pair]


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
