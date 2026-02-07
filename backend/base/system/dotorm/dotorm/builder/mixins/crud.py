"""CRUD operations mixin."""

from typing import TYPE_CHECKING, Any, Literal

from ...components.filter_parser import FilterExpression

if TYPE_CHECKING:
    from ..protocol import BuilderProtocol

from ..helpers import (
    build_sql_create_from_schema,
    build_sql_update_from_schema,
)


# Allowed order values (uppercase for comparison)
_ALLOWED_ORDER = frozenset({"ASC", "DESC"})


class CRUDMixin:
    """
    Mixin providing basic CRUD query builders.

    Builder работает с dict, а не с моделью.
    Сериализация модели в dict происходит в ORM слое.

    Expects: table, fields, dialect, get_store_fields(), filter_parser
    """

    __slots__ = ()

    def build_delete(self: "BuilderProtocol") -> str:
        return f"DELETE FROM {self.table} WHERE id=%s"

    def build_delete_bulk(self: "BuilderProtocol", count: int) -> str:
        """Build bulk DELETE by ids.

        Postgres: ANY($1::int[]) — single array param, no parse overhead.
        MySQL:    IN (%s, %s, ...) — individual params (no array type).
        """
        if self.dialect.name == "postgres":
            return f"DELETE FROM {self.table} WHERE id = ANY($1::int[])"

        placeholders = self.dialect.make_placeholders(count)
        return f"DELETE FROM {self.table} WHERE id IN ({placeholders})"

    def build_create(
        self: "BuilderProtocol",
        payload_dict: dict[str, Any],
    ) -> tuple[str, tuple]:
        """Build INSERT query from dict."""
        stmt = f"INSERT INTO {self.table} (%s) VALUES (%s)"
        stmt, values_list = build_sql_create_from_schema(stmt, payload_dict)
        return stmt, values_list

    # Mapping of SQL types to PostgreSQL array cast types for unnest
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

    def _get_pg_array_type(self: "BuilderProtocol", sql_type: str) -> str:
        """Map SQL type to PostgreSQL array cast type for unnest."""
        # Exact match
        upper = sql_type.upper()
        if upper in self._PG_ARRAY_TYPE_MAP:
            return self._PG_ARRAY_TYPE_MAP[upper]
        # VARCHAR(N) -> text
        if upper.startswith("VARCHAR"):
            return "text"
        # DECIMAL(M,N) -> numeric
        if upper.startswith("DECIMAL"):
            return "numeric"
        # Fallback
        return "text"

    def build_create_bulk(
        self: "BuilderProtocol",
        payloads_dicts: list[dict[str, Any]],
    ) -> tuple[str, list]:
        """Build bulk INSERT query.

        Postgres: unnest approach — one array param per column.
          INSERT INTO t (a, b, c) SELECT * FROM unnest($1::text[], $2::int4[], $3::bool[])
          For 5000 rows × 10 fields = 10 params instead of 50,000.

        MySQL: VALUES (%s,%s,...), (%s,%s,...) — individual params.
        """
        if not payloads_dicts:
            raise ValueError("payloads_dicts cannot be empty")

        fields_list = list(payloads_dicts[0].keys())

        if self.dialect.name == "postgres":
            return self._build_create_bulk_unnest(payloads_dicts, fields_list)

        return self._build_create_bulk_values(payloads_dicts, fields_list)

    def _build_create_bulk_unnest(
        self: "BuilderProtocol",
        payloads_dicts: list[dict[str, Any]],
        fields_list: list[str],
    ) -> tuple[str, list]:
        """Postgres: INSERT ... SELECT * FROM unnest($1::type[], $2::type[], ...)"""
        query_columns = ", ".join(fields_list)

        # Build column arrays (transpose rows→columns)
        column_arrays = []
        unnest_params = []
        for i, field_name in enumerate(fields_list, 1):
            col_values = [row[field_name] for row in payloads_dicts]
            column_arrays.append(col_values)

            # Get PostgreSQL array type from field definition
            field_obj = self.fields.get(field_name)
            if field_obj:
                # sql_type can be class attr (str) or property
                sql_type = field_obj.sql_type
                pg_type = self._get_pg_array_type(sql_type)
            else:
                pg_type = "text"
            unnest_params.append(f"${i}::{pg_type}[]")

        unnest_clause = ", ".join(unnest_params)
        stmt = (
            f"INSERT INTO {self.table} ({query_columns}) "
            f"SELECT * FROM unnest({unnest_clause})"
        )
        return stmt, column_arrays

    def _build_create_bulk_values(
        self: "BuilderProtocol",
        payloads_dicts: list[dict[str, Any]],
        fields_list: list[str],
    ) -> tuple[str, list]:
        """MySQL/Clickhouse: INSERT ... VALUES (%s,%s,...), (%s,%s,...), ..."""
        query_columns = ", ".join(fields_list)
        num_fields = len(fields_list)

        all_values = []
        value_groups = []
        placeholder_group = f"({self.dialect.make_placeholders(num_fields)})"

        for payload_dict in payloads_dicts:
            for field in fields_list:
                all_values.append(payload_dict[field])
            value_groups.append(placeholder_group)

        values_clause = ", ".join(value_groups)
        stmt = f"INSERT INTO {self.table} ({query_columns}) VALUES {values_clause}"
        return stmt, all_values

    def build_update(
        self: "BuilderProtocol",
        payload_dict: dict[str, Any],
        id: int,
    ) -> tuple[str, tuple]:
        """Build UPDATE query from dict."""
        stmt = f"UPDATE {self.table} SET %s WHERE id = %s"
        stmt, values_list = build_sql_update_from_schema(
            stmt, payload_dict, id
        )
        return stmt, values_list

    def build_update_bulk(
        self: "BuilderProtocol",
        payload_dict: dict[str, Any],
        ids: list[int],
    ) -> tuple[str, tuple]:
        """Build bulk UPDATE query.

        Postgres: WHERE id = ANY($N::int[]) — ids as single array param.
        MySQL:    WHERE id IN (%s, %s, ...) — ids as individual params.
        """
        if not payload_dict:
            raise ValueError("payload_dict cannot be empty")

        fields_list = list(payload_dict.keys())
        values_list = [payload_dict[f] for f in fields_list]

        # SET field1=%s, field2=%s
        set_clause = ", ".join(f"{field}=%s" for field in fields_list)

        if self.dialect.name == "postgres":
            # ids as single array parameter: ANY($N::int[])
            values_list.append(ids)
            stmt = (
                f"UPDATE {self.table} SET {set_clause} "
                f"WHERE id = ANY(%s::int[])"
            )
        else:
            # ids as individual parameters: IN (%s, %s, ...)
            placeholders = self.dialect.make_placeholders(len(ids))
            values_list.extend(ids)
            stmt = (
                f"UPDATE {self.table} SET {set_clause} "
                f"WHERE id IN ({placeholders})"
            )

        return stmt, tuple(values_list)

    def build_get(
        self: "BuilderProtocol",
        id: int,
        fields: list[str] | None = None,
    ) -> tuple[str, list]:
        """
        Build SELECT by ID query.

        Args:
            id: Record ID
            fields: Fields to select (empty = all stored)
        """
        escape = self.dialect.escape
        store_fields = self.get_store_fields()

        selected_fields = fields if fields else store_fields
        fields_stmt = ", ".join(
            f"{escape}{name}{escape}" for name in selected_fields
        )

        stmt = f"SELECT {fields_stmt} FROM {self.table} WHERE id = %s LIMIT 1"
        return stmt, [id]

    def build_table_len(self: "BuilderProtocol") -> tuple[str, None]:
        stmt = f"SELECT COUNT(*) FROM {self.table}"
        return stmt, None

    def build_search(
        self: "BuilderProtocol",
        fields: list[str] | None = None,
        start: int | None = None,
        end: int | None = None,
        limit: int = 80,
        order: Literal["DESC", "ASC", "desc", "asc"] | None = None,
        sort: str | None = None,
        filter: FilterExpression | None = None,
        raw: bool = False,
    ) -> tuple[str, tuple]:
        """
        Build search query.

        Args:
            fields: Fields to select (default: ["id"])
            start: Offset start
            end: Offset end
            limit: Max records
            order: Sort order (ASC/DESC)
            sort: Sort field
            filter: Filter expression
            raw: Return raw dict instead of model
        """
        escape = self.dialect.escape
        store_fields = self.get_store_fields()

        if fields is None:
            fields = store_fields

        # поставить защиту, хотя по идее защита есть в ОРМ
        if order:
            order_upper = order.upper()
            if order_upper not in _ALLOWED_ORDER:
                raise ValueError(f"Invalid order: {order}")
        if sort and sort not in store_fields:
            sort = store_fields[0]
            # raise ValueError(f"Invalid sort field: {sort}")

        # Always include 'id' — without it, deserialized objects have
        # Field descriptor instead of int, which breaks update()/delete().
        fields_with_id = fields if "id" in fields else ["id", *fields]

        fields_store_stmt = ", ".join(
            f"{escape}{name}{escape}"
            for name in fields_with_id
            if name in store_fields
        )

        where = ""
        where_values: tuple = ()

        if filter:
            where_clause, where_values = self.filter_parser.parse(filter)
            where = f"WHERE {where_clause}"

        stmt = f"SELECT {fields_store_stmt} FROM {self.table} " f"{where} "
        if sort and order:
            stmt += f"ORDER BY {sort} {order_upper} "

        val: tuple = ()

        if end is not None and start is not None:
            stmt += "LIMIT %s OFFSET %s"
            val = (end - start, start)
        elif limit:
            stmt += "LIMIT %s"
            val = (limit,)

        # Prepend where values
        if where_values:
            val = where_values + val

        return stmt, val

    def build_search_count(
        self: "BuilderProtocol",
        filter: FilterExpression | None = None,
    ) -> tuple[str, tuple]:
        """
        Build COUNT query with filter.

        Args:
            filter: Filter expression

        Returns:
            Tuple of (query, values)
        """
        where = ""
        where_values: tuple = ()

        if filter:
            where_clause, where_values = self.filter_parser.parse(filter)
            where = f"WHERE {where_clause}"

        stmt = f"SELECT COUNT(*) as count FROM {self.table} {where}"

        return stmt, where_values

    def build_exists(
        self: "BuilderProtocol",
        filter: FilterExpression | None = None,
    ) -> tuple[str, tuple]:
        """
        Build EXISTS query with filter.

        Args:
            filter: Filter expression

        Returns:
            Tuple of (query, values)
        """
        where = ""
        where_values: tuple = ()

        if filter:
            where_clause, where_values = self.filter_parser.parse(filter)
            where = f"WHERE {where_clause}"

        stmt = f"SELECT 1 FROM {self.table} {where} LIMIT 1"

        return stmt, where_values
