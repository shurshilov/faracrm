"""Many2many query builder."""

from typing import TYPE_CHECKING, Literal, Type


if TYPE_CHECKING:
    from ..protocol import BuilderProtocol
    from ...model import DotModel


class Many2ManyMixin:
    """Mixin for many-to-many relation queries."""

    __slots__ = ()

    def build_get_many2many(
        self: "BuilderProtocol",
        id: int,
        relation_table: Type["DotModel"],
        many2many_table: str,
        column1: str,
        column2: str,
        fields: list[str],
        order: Literal["desc", "asc"] = "desc",
        start: int | None = None,
        end: int | None = None,
        sort: str = "id",
        limit: int | None = 10,
    ) -> tuple[str, tuple]:
        """Build SELECT for M2M relation."""
        if not fields:
            fields = relation_table.get_store_fields()

        # явно указать для sql запроса что эти поля относятся
        # к связанной таблице
        fields_prefixed = [f"p.{field}" for field in fields]
        fields_select_stmt = ", ".join(fields_prefixed)

        stmt = f"""
        SELECT {fields_select_stmt}
        FROM {relation_table.__table__} p
        JOIN {many2many_table} pt ON p.id = pt.{column1}
        JOIN {self.table} t ON pt.{column2} = t.id
        WHERE t.id = %s
        ORDER BY {sort} {order}
        """

        val: tuple = (id,)

        if end is not None and start is not None:
            stmt += "LIMIT %s OFFSET %s"
            val += (end - start, start)
        elif limit:
            stmt += "LIMIT %s"
            val += (limit,)

        return stmt, val

    def build_get_many2many_multiple(
        self: "BuilderProtocol",
        ids: list[int],
        relation_table: Type["DotModel"],
        many2many_table: str,
        column1: str,
        column2: str,
        fields: list[str] | None = None,
        limit: int = 80,
    ) -> tuple[str, tuple]:
        """
        Оптимизированная версия, когда необходимо получить сразу несколько свзяей m2m
        у нескольких записей. Не просто один список на одну записиь.
        А N списков на N записей.

        Returns:
            tuple[str, tuple]: SQL statement and parameter values
        """
        if not fields:
            fields = relation_table.get_store_fields()

        # явно указать для sql запроса что эти поля относятся
        # к связанной таблице
        fields_prefixed = [f"p.{field}" for field in fields]

        # добавляем ид из таблицы связи для последующего маппинга записей
        # имеется ввиду за один запрос достаются все записи для всех ид
        # а далее в питоне для каждого ид остаются только его
        fields_prefixed.append(f"pt.{column2} as m2m_id")

        fields_select_stmt = ", ".join(fields_prefixed)
        query_placeholders = ", ".join(["%s"] * len(ids))

        stmt = f"""
        SELECT {fields_select_stmt}
        FROM {relation_table.__table__} p
        JOIN {many2many_table} pt ON p.id = pt.{column1}
        JOIN {self.table} t ON pt.{column2} = t.id
        WHERE t.id IN ({query_placeholders})
        LIMIT %s
        """

        val = (*ids, limit)
        return stmt, val


#         SELECT * FROM (
#     SELECT p.*, pt.column2 as m2m_id,
#            ROW_NUMBER() OVER (PARTITION BY pt.column2 ORDER BY p.id) as rn
#     FROM relation_table p
#     JOIN m2m_table pt ON p.id = pt.column1
#     WHERE pt.column2 IN (%s, %s, ...)
# ) sub WHERE rn <= {limit_per_parent}
