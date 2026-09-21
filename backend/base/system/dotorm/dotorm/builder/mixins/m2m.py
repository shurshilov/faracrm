"""Many2many query builder."""

from typing import TYPE_CHECKING, Literal, Type

if TYPE_CHECKING:
    from ..protocol import BuilderProtocol
    from ...model import DotModel


class Many2ManyMixin:
    """Mixin for many-to-many relation queries."""

    __slots__ = ()

    @staticmethod
    def _m2m_filter_clause(
        relation_table: Type["DotModel"], filter: list | None
    ) -> tuple[str, tuple]:
        """Field.filter у Many2many → доп. условие на связанную таблицу.

        В M2M-запросе три таблицы под алиасами, а FilterParser пишет голые
        имена колонок, поэтому фильтр не вклеиваем в общий WHERE, а сужаем
        связанную таблицу подзапросом по её id: там имена однозначны.
        Парсер связанной модели заодно проверяет имена полей фильтра.
        """
        if not filter:
            return "", ()
        clause, values = relation_table._builder.filter_parser.parse(filter)
        return (
            f" AND p.id IN (SELECT id FROM {relation_table.__table__} "
            f"WHERE {clause})",
            tuple(values),
        )

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
        limit: int | None = None,
        filter: list | None = None,
    ) -> tuple[str, tuple]:
        """Build SELECT for M2M relation. LIMIT только явный (см. get_many2many)."""
        store_fields = relation_table.get_store_fields()
        if not fields:
            fields = store_fields

        if sort not in store_fields:
            sort = "id"

        # явно указать для sql запроса что эти поля относятся
        # к связанной таблице
        fields_prefixed = [f"p.{field}" for field in fields]
        fields_select_stmt = ", ".join(fields_prefixed)
        filter_clause, filter_values = self._m2m_filter_clause(
            relation_table, filter
        )

        # ORDER BY с алиасом: без него «id» неоднозначен между p и t, когда
        # его нет в списке выбранных полей (AmbiguousColumnError).
        stmt = f"""
        SELECT {fields_select_stmt}
        FROM {relation_table.__table__} p
        JOIN {many2many_table} pt ON p.id = pt.{column1}
        JOIN {self.table} t ON pt.{column2} = t.id
        WHERE t.id = %s{filter_clause}
        ORDER BY p.{sort} {order}
        """

        val: tuple = (id, *filter_values)

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
        filter: list | None = None,
    ) -> tuple[str, tuple]:
        """
        Оптимизированная версия, когда необходимо получить сразу несколько свзяей m2m
        у нескольких записей. Не просто один список на одну записиь.
        А N списков на N записей.

        Без LIMIT: объём уже ограничен ids родителей (страница списка), а
        общий LIMIT на весь join обрезал связи у последних строк страницы.
        ORDER BY p.id — детерминированный порядок связей у каждого родителя.

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
        filter_clause, filter_values = self._m2m_filter_clause(
            relation_table, filter
        )

        stmt = f"""
        SELECT {fields_select_stmt}
        FROM {relation_table.__table__} p
        JOIN {many2many_table} pt ON p.id = pt.{column1}
        JOIN {self.table} t ON pt.{column2} = t.id
        WHERE t.id IN ({query_placeholders}){filter_clause}
        ORDER BY p.id
        """

        val = (*ids, *filter_values)
        return stmt, val
