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
        args = ",".join(["%s"] * count)
        return f"DELETE FROM {self.table} WHERE id IN ({args})"

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
        """Build bulk INSERT query with multiple VALUES."""
        if not payloads_dicts:
            raise ValueError("payloads_dicts cannot be empty")

        # Берём ключи из первого payload
        fields_list = list(payloads_dicts[0].keys())
        query_columns = ", ".join(fields_list)

        # Собираем все значения в плоский список
        all_values = []
        value_groups = []
        param_index = 1

        for payload_dict in payloads_dicts:
            placeholders = []
            for field in fields_list:
                placeholders.append(f"${param_index}")
                all_values.append(payload_dict[field])
                param_index += 1
            value_groups.append(f"({', '.join(placeholders)})")

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
        """Build bulk UPDATE query from dict."""
        stmt = f"UPDATE {self.table} SET %s WHERE id IN (%s)"
        stmt, values_list = build_sql_update_from_schema(
            stmt, payload_dict, ids
        )
        return stmt, values_list

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
        order: Literal["DESC", "ASC", "desc", "asc"] = "DESC",
        sort: str = "id",
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
        order_upper = order.upper()
        if order_upper not in _ALLOWED_ORDER:
            raise ValueError(f"Invalid order: {order}")
        if sort not in store_fields:
            sort = store_fields[0]
            # raise ValueError(f"Invalid sort field: {sort}")

        fields_store_stmt = ", ".join(
            f"{escape}{name}{escape}"
            for name in fields
            if name in store_fields
        )

        where = ""
        where_values: tuple = ()

        if filter:
            where_clause, where_values = self.filter_parser.parse(filter)
            where = f"WHERE {where_clause}"

        stmt = (
            f"SELECT {fields_store_stmt} FROM {self.table} "
            f"{where} ORDER BY {sort} {order_upper} "
        )

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
