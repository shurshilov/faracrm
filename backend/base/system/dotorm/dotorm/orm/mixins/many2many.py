"""Many2many ORM operations mixin."""

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ..protocol import DotModelProtocol

    _Base = DotModelProtocol
else:
    _Base = object

from ...access import Operation
from ...fields import (
    PolymorphicMany2one,
    Many2many,
    Many2one,
    One2many,
    One2one,
    PolymorphicOne2many,
)
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
        limit: int | None = None,
        session=None,
        filter: list | None = None,
    ):
        # limit по умолчанию None: скрытый LIMIT 10 молча обрезал связи у
        # вызывающих без явного лимита; страницу задаёт роут search_many2many.
        if not fields:
            fields = []
        session = cls._get_db_session(session)
        # защита, оставить только те поля, которые действительно хранятся в базе
        fields_store = [
            name for name in comodel.get_store_fields() if name in fields
        ]
        if not fields_store:
            fields_store = comodel.get_store_fields()
        # role_read связанной модели: закрытые поля не читаем, фильтр и
        # сортировка по ним — ошибка, как в её собственном поиске.
        fields_store = await comodel._check_field_access(
            Operation.READ, fields_store, filter, sort
        )
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
            filter=filter,
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
        """Link records in M2M relation.

        Идемпотентно: ON CONFLICT DO NOTHING (Postgres) и INSERT IGNORE (MySQL)
        отбрасывают пары, которые уже есть в связующей таблице (защита от
        дублей - сидеры на каждом старте, повторные e2e-прогоны, повторная
        привязка той же пары)
        """
        cls = self.__class__
        session = cls._get_db_session(session)
        if not values:
            return None
        escape = cls._dialect.escape_identifier
        if cls._dialect.name == "postgres":
            verb, on_conflict = "INSERT", "ON CONFLICT DO NOTHING"
        else:
            verb, on_conflict = "INSERT IGNORE", ""
        # Все пары (column2, column1) одним запросом — unnest двух массивов
        # или VALUES (...), ... — а не executemany построчно: N связей =
        # один round-trip.
        source, bind = cls._dialect.make_link_pairs_source(values)
        stmt = (
            f"{verb} INTO {escape(field.many2many_table)} "
            f"({escape(field.column2)}, {escape(field.column1)}) "
            f"{source} {on_conflict}"
        )
        return await session.execute(stmt, bind, cursor="void")

    @classmethod
    async def unlink_many2many(
        cls,
        field: Many2many,
        ids: list[int],
        owner_ids: list[int],
        session=None,
    ):
        """Отвязать записи M2M ТОЛЬКО у конкретных владельцев (owner_ids
        одним DELETE."""
        if not ids:
            return None
        session = cls._get_db_session(session)
        escape = cls._dialect.escape_identifier
        args = cls._dialect.make_placeholders(len(ids))
        owner_args = cls._dialect.make_placeholders(len(owner_ids))
        stmt = (
            f"DELETE FROM {escape(field.many2many_table)} "
            f"WHERE {escape(field.column1)} IN ({args}) "
            f"AND {escape(field.column2)} IN ({owner_args})"
        )
        return await session.execute(stmt, [*ids, *owner_ids])

    @classmethod
    async def _nested_fields_allowed(
        cls, fields_relation, fields_nested: dict[str, dict] | None
    ) -> dict[str, dict]:
        """fields_nested, где у каждой связи поля связанной модели оставлены
        после field-level проверки чтения (role_read) для текущей сессии.
        Без вложенного списка проверяется дефолт билдера — все store-поля."""
        result: dict[str, dict] = dict(fields_nested or {})
        for name, field in fields_relation:
            related = field.relation_table
            if related is None:
                continue
            nested = result.get(name)
            requested = (
                field.nested_fields(nested) or related.get_store_fields()
            )
            allowed = await related._check_field_access(
                Operation.READ, requested, field.nested_filter(nested)
            )
            # id нужен всегда: по нему связь раскладывается по записям
            if "id" not in allowed:
                allowed = ["id", *allowed]
            result[name] = {**(nested or {}), "fields": allowed}
        return result

    @classmethod
    async def _records_list_get_relation(
        cls,
        session,
        fields_relation,
        records,
        fields_nested: dict[str, dict] | None = None,
    ):
        """Load relations for a list of records (batch)."""
        cls._dialect

        # role_read связанной модели — как в её собственном поиске: закрытые
        # сессии поля вырезаются и из вложенного списка, и из дефолта «все
        # store-поля» (иначе связь поднимала бы их в обход проверки), фильтр
        # по ним — ошибка. Билдеру уходит уже проверенный список.
        fields_nested = await cls._nested_fields_allowed(
            fields_relation, fields_nested
        )

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
                # Build lookup dict: id → related object
                result_by_id = {
                    res_model.id: res_model for res_model in result
                }
                # Map related objects to records. Под non-data Field-descriptor
                # getattr на не-назначенном поле возвращает None — отдельная
                # ветка «is Field» не нужна, result_by_id.get(None) тоже None.
                for rec in records:
                    fk_id = getattr(rec, req.field_name)
                    setattr(rec, req.field_name, result_by_id.get(fk_id))

            # PolymorphicOne2many — как One2many: relation_table_field = res_id
            if isinstance(req.field, (One2many, One2one, PolymorphicOne2many)):
                # Build lookup: parent_id → [children]
                children: dict[int, list] = {}
                for res_model in result:
                    parent_id = getattr(
                        res_model, req.field.relation_table_field
                    )
                    children.setdefault(parent_id, []).append(res_model)
                # Map to records
                for rec in records:
                    rows = children.get(rec.id, [])
                    if isinstance(req.field, One2one):
                        # одна строка на запись: объект или None
                        setattr(rec, req.field_name, rows[0] if rows else None)
                    else:
                        setattr(rec, req.field_name, rows)

            if isinstance(req.field, Many2many):
                # Build lookup: parent_id → [related]
                m2m_map: dict[int, list] = {}
                for res_model in result:
                    m2m_map.setdefault(res_model.m2m_id, []).append(res_model)
                # Map to records
                for rec in records:
                    # old_value = getattr(rec, req.field_name)
                    # if isinstance(old_value, Field):
                    #     setattr(rec, req.field_name, m2m_map.get(rec.id, []))
                    # else:
                    setattr(rec, req.field_name, m2m_map.get(rec.id, []))
                # Удаляем служебный атрибут m2m_id
                for res_model in result:
                    del res_model.__dict__["m2m_id"]
