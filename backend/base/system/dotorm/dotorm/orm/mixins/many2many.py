"""Many2many ORM operations mixin."""

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ..protocol import DotModelProtocol

    _Base = DotModelProtocol
else:
    _Base = object

from ...fields import PolymorphicMany2one, Field, Many2many, Many2one, One2many
from ...decorators import hybridmethod
from ..utils import execute_maybe_parallel


class OrmMany2manyMixin(_Base):
    """
    Mixin providing ORM operations for many-to-many relations.

    Provides:
    - get_many2many - fetch M2M related records
    - link_many2many - create M2M links
    - unlink_many2many - remove M2M links
    - _records_list_get_relation - batch load relations

    Expects DotModel to provide:
    - _get_db_session()
    - _builder
    - _dialect
    - get_relation_fields()
    - prepare_list_ids()
    """

    @classmethod
    async def get_many2many(
        cls,
        id,
        comodel,
        relation,
        column1,
        column2,
        fields=None,
        order: Literal["desc", "asc"] = "desc",
        start: int | None = None,
        end: int | None = None,
        sort: str = "id",
        limit: int | None = 10,
        session=None,
    ):
        if not fields:
            fields = []
        session = cls._get_db_session(session)
        # защита, оставить только те поля, которые действительно хранятся в базе
        fields_store = [
            name for name in comodel.get_store_fields() if name in fields
        ]
        if not fields_store:
            fields_store = comodel.get_store_fields()
        stmt, values = cls._builder.build_get_many2many(
            id,
            comodel,
            relation,
            column1,
            column2,
            fields_store,
            order,
            start,
            end,
            sort,
            limit,
        )
        records = await session.execute(
            stmt, values, prepare=comodel.prepare_list_ids
        )

        # если есть хоть одна запись и вообще нужно читать поля связей
        fields_relation = [
            (name, field)
            for name, field in comodel.get_relation_fields()
            if name in fields
        ]
        if records and fields_relation:
            await cls._records_list_get_relation(
                session, fields_relation, records
            )
        return records

    @hybridmethod
    async def link_many2many(
        self, field: Many2many, values: list, session=None
    ):
        """Link records in M2M relation."""
        cls = self.__class__
        session = cls._get_db_session(session)
        query_placeholders = ", ".join(["%s"] * len(values[0]))
        stmt = f"""INSERT INTO {field.many2many_table}
        ({field.column2}, {field.column1})
        VALUES
        ({query_placeholders})
        """
        return await session.execute(stmt, [values], cursor="executemany")

    @classmethod
    async def unlink_many2many(cls, field: Many2many, ids: list, session=None):
        """Unlink records from M2M relation."""
        session = cls._get_db_session(session)
        args: str = ",".join(["%s"] * len(ids))
        stmt = f"DELETE FROM {field.many2many_table} WHERE {field.column1} in ({args})"
        return await session.execute(stmt, ids)

    @classmethod
    async def _records_list_get_relation(
        cls,
        session,
        fields_relation,
        records,
        fields_nested: dict[str, list[str]] | None = None,
    ):
        """Load relations for a list of records (batch)."""
        dialect = cls._dialect

        request_list = cls._builder.build_search_relation(
            fields_relation, records, fields_nested
        )
        execute_list = [
            session.execute(
                req.stmt,
                req.value,
                prepare=req.function_prepare,
                cursor=req.function_cursor,
            )
            for req in request_list
        ]
        # выполняем последовательно в транзакции, параллельно вне транзакции
        results = await execute_maybe_parallel(execute_list)

        # маппинг (полученных оптимизированных запросов) полей связей
        # на конкретные записи (полученные при чтении store на предыдущем шаге)
        for index, result in enumerate(results):
            req = request_list[index]

            if isinstance(req.field, (Many2one, PolymorphicMany2one)):
                # Сначала инициализируем все записи None
                for rec in records:
                    rec_field_raw = getattr(rec, req.field_name)
                    if isinstance(rec_field_raw, Field):
                        setattr(rec, req.field_name, None)
                # Теперь маппим найденные результаты
                for rec in records:
                    rec_field_raw = getattr(rec, req.field_name)
                    for res_model in result:
                        if rec_field_raw == res_model.id:
                            setattr(rec, req.field_name, res_model)
                            break

            if isinstance(req.field, One2many):
                # Сначала инициализируем все записи пустым списком
                for rec in records:
                    old_value = getattr(rec, req.field_name)
                    if isinstance(old_value, Field):
                        setattr(rec, req.field_name, [])
                # Теперь добавляем найденные результаты
                for res_model in result:
                    res_field_id = getattr(
                        res_model, req.field.relation_table_field
                    )
                    for rec in records:
                        if rec.id == res_field_id:
                            getattr(rec, req.field_name).append(res_model)
                            break

            if isinstance(req.field, Many2many):
                # Сначала инициализируем все записи пустым списком
                for rec in records:
                    old_value = getattr(rec, req.field_name)
                    if isinstance(old_value, Field):
                        setattr(rec, req.field_name, [])
                # Теперь добавляем найденные результаты
                for res_model in result:
                    for rec in records:
                        if rec.id == res_model.m2m_id:
                            getattr(rec, req.field_name).append(res_model)
                            break
                # Удаляем служебный атрибут m2m_id
                for res_model in result:
                    del res_model.__dict__["m2m_id"]
