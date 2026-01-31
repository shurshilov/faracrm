"""Relations query builder."""

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from ..protocol import BuilderProtocol

from ..request_builder import RequestBuilder
from ...fields import PolymorphicMany2one, Field, Many2many, Many2one, One2many


class RelationsMixin:
    """Mixin for relation queries."""

    __slots__ = ()

    def build_search_relation(
        self: "BuilderProtocol",
        fields_relation: list[tuple[str, Field]],
        records: list | None = None,
        fields_nested: dict[str, list[str]] | None = None,
    ) -> list[RequestBuilder]:
        """
        Build optimized queries for loading relations.
        Avoids N+1 by batching relation queries.
        """
        if records is None:
            records = []

        request_list: list[RequestBuilder] = []
        ids: list[int] = [record.id for record in records]

        if not ids:
            return request_list

        for name, field in fields_relation:
            # TODO: взможно ошибка от дублирвоания полей
            # Default fields for relations
            # добавить вложенные поля от пользователя
            fields = []
            if fields_nested:
                custom_fields = fields_nested.get(name)
                if custom_fields:
                    fields += custom_fields
            if field.relation_table:
                fields = field.relation_table.get_store_fields()

            req: RequestBuilder | None = None

            if isinstance(field, One2many):
                stmt, val = field.relation_table._builder.build_search(
                    fields=[*fields, field.relation_table_field],
                    filter=[(field.relation_table_field, "in", ids)],
                )
                req = RequestBuilder(
                    stmt=stmt,
                    value=val,
                    field_name=name,
                    field=field,
                    fields=fields,
                )

            elif isinstance(field, Many2many):
                stmt, val = self.build_get_many2many_multiple(
                    ids=ids,
                    relation_table=field.relation_table,
                    many2many_table=field.many2many_table,
                    column1=field.column1,
                    column2=field.column2,
                    fields=fields,
                )
                req = RequestBuilder(
                    stmt=stmt,
                    value=val,
                    field_name=name,
                    field=field,
                )

            elif isinstance(field, (Many2one, PolymorphicMany2one)):
                ids_m2o: list[int] = [
                    getattr(record, name)
                    for record in records
                    if getattr(record, name) is not None  # Фильтруем None
                ]
                # оставляем только уникальные ид, так как в m2o несколько записей
                # могут ссылаться на одну сущность
                ids_m2o = list(set(ids_m2o))

                # Если нет ни одного ID — пропускаем
                if not ids_m2o:
                    continue
                stmt, val = field.relation_table._builder.build_search(
                    fields=fields,
                    filter=[("id", "in", ids_m2o)],
                )
                req = RequestBuilder(
                    stmt=stmt,
                    value=val,
                    field_name=name,
                    field=field,
                )

            if req:
                request_list.append(req)

        return request_list
