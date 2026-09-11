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

    Dialect-specific statement shapes (bulk insert/update/delete) are delegated
    to self.dialect — the mixin stays free of per-database branching.

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
        return (
            f"DELETE FROM {self.table} "
            f"WHERE {self.dialect.make_ids_predicate(count, ids_first=True)}"
        )

    def build_create(
        self: "BuilderProtocol",
        payload_dict: dict[str, Any],
    ) -> tuple[str, tuple]:
        """Build INSERT query from dict."""
        stmt = f"INSERT INTO {self.table} (%s) VALUES (%s)"
        stmt, values_list = build_sql_create_from_schema(stmt, payload_dict)
        return stmt, values_list

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
        columns = ", ".join(fields_list)

        # Dialect fills the source clause after "INSERT INTO t (cols)":
        # unnest(...) for Postgres, VALUES (...), ... for MySQL.
        source, values = self.dialect.make_bulk_insert_source(
            payloads_dicts, fields_list, self.fields
        )
        stmt = f"INSERT INTO {self.table} ({columns}) {source}"
        return stmt, values

    def build_update(
        self: "BuilderProtocol",
        payload_dict: dict[str, Any],
        id: int,
    ) -> tuple[str, tuple]:
        """Build UPDATE query from dict.

        Передаёт self.fields в helper — поля сами генерируют свои
        SQL-фрагменты через to_sql_update (см. Field API).
        """
        stmt = f"UPDATE {self.table} SET %s WHERE id = %s"
        stmt, values_list = build_sql_update_from_schema(
            stmt, payload_dict, id, self.fields
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

        # SET field1=%s, field2=%s (dialect-agnostic)
        set_clause = ", ".join(f"{field}=%s" for field in fields_list)

        stmt = (
            f"UPDATE {self.table} SET {set_clause} "
            f"WHERE {self.dialect.make_ids_predicate(len(ids))}"
        )
        values = tuple(values_list) + tuple(self.dialect.bind_ids(ids))
        return stmt, values

    def build_update_bulk_rows(
        self: "BuilderProtocol",
        rows: list[dict[str, Any]],
    ) -> tuple[str, list] | None:
        """Bulk UPDATE с РАЗНЫМИ значениями на строку — одним запросом.

        rows: [{"id": .., f1: .., ...}, ...] — один и тот же набор полей.
        Postgres: UPDATE t SET f = v.f FROM unnest(...) AS v(id, f)
        WHERE t.id = v.id. None — у диалекта нет такой формы
        (MySQL/ClickHouse): вызывающий обновляет построчно.
        """
        if not rows:
            raise ValueError("rows cannot be empty")
        fields_list = [name for name in rows[0] if name != "id"]
        if not fields_list:
            raise ValueError("rows must contain fields besides id")
        made = self.dialect.make_bulk_update_rows(
            rows, fields_list, self.fields
        )
        if made is None:
            return None
        set_clause, from_clause, values = made
        stmt = (
            f"UPDATE {self.table} SET {set_clause} {from_clause} "
            f"WHERE {self.table}.id = v.id"
        )
        return stmt, values

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
        limit: int | None = None,
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

        # Pagination: start/end → LIMIT (end-start) OFFSET start
        # limit alone → LIMIT limit
        # start alone → OFFSET start (no limit)
        if start is not None and end is not None:
            stmt += "LIMIT %s OFFSET %s"
            val = (end - start, start)
        elif start is not None and limit is not None:
            stmt += "LIMIT %s OFFSET %s"
            val = (limit, start)
        elif limit is not None:
            stmt += "LIMIT %s"
            val = (limit,)
        elif start is not None:
            stmt += "OFFSET %s"
            val = (start,)

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
