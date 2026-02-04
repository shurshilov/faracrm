"""Relations ORM operations mixin."""

from typing import TYPE_CHECKING, Any, Literal, Self, TypeVar

from ...components.filter_parser import FilterExpression
from ...decorators import hybridmethod
from ...access import Operation
from ...fields import (
    PolymorphicMany2one,
    PolymorphicOne2many,
    Field,
    Many2many,
    Many2one,
    One2many,
    One2one,
)
from ..utils import execute_maybe_parallel

if TYPE_CHECKING:
    from ..protocol import DotModelProtocol
    from ...model import DotModel

    _Base = DotModelProtocol
else:
    _Base = object

# TypeVar for generic payload - accepts any DotModel subclass
_M = TypeVar("_M", bound="DotModel")


class OrmRelationsMixin(_Base):
    """
    Mixin providing ORM operations for relations.

    Provides:
    - search - search records with relation loading
    - search_count - count records matching filter
    - exists - have one record or not
    - _get_load_relations - load relations for single record (used by get())
    - _update_relations - update record with relations (used by update())

    Expects DotModel to provide:
    - _get_db_session()
    - _builder
    - _dialect
    - __table__
    - get_fields(), get_store_fields(), get_relation_fields()
    - get_relation_fields_m2m_o2m(), get_relation_fields_attachment()
    - prepare_list_ids()
    - get_many2many(), link_many2many(), unlink_many2many()
    - _records_list_get_relation()
    - update()
    """

    @hybridmethod
    async def search(
        self,
        fields: list[str] | None = None,
        fields_nested: dict[str, list[str]] | None = None,
        start: int | None = None,
        end: int | None = None,
        limit: int = 1000,
        order: Literal["DESC", "ASC", "desc", "asc"] = "DESC",
        sort: str = "id",
        filter: FilterExpression | None = None,
        raw: bool = False,
        session=None,
    ) -> list[Self]:
        """
        Поиск записей с поддержкой фильтрации, пагинации и загрузки relations.

        Выполняет оптимизированные batch-запросы для relation полей:
        один запрос на тип relation для всех найденных записей.

        Args:
            fields: Список полей для загрузки (store + relation).
                   По умолчанию ["id"].
            start: Начальный индекс для пагинации (OFFSET)
            end: Конечный индекс (не используется напрямую, см. limit)
            limit: Максимальное количество записей. По умолчанию 1000.
            order: Направление сортировки "DESC" или "ASC"
            sort: Поле для сортировки. По умолчанию "id".
            filter: Фильтр в формате FilterExpression.
                   Например: [("active", "=", True), ("name", "ilike", "%test%")]
            raw: Если True - возвращает сырые данные без преобразования в модели
            session: DB сессия (опционально)

        Returns:
            Список экземпляров модели с загруженными данными.
            Relation поля инициализируются:
            - Many2one → модель или None
            - One2many → список моделей или []
            - Many2many → список моделей или []

        Example:
            # Найти активных пользователей с их ролями
            users = await User.search(
                fields=["id", "name", "email", "role_ids"],
                filter=[("active", "=", True)],
                limit=50,
                order="ASC",
                sort="name"
            )

            for user in users:
                if user.role_ids:  # Корректно работает ([] если пусто)
                    print(f"{user.name}: {len(user.role_ids)} roles")

        Note:
            Relations загружаются batch-запросами (один запрос на тип relation
            для всех найденных записей). Для одной записи используйте
            get(id, fields, fields_nested).
        """
        cls = self.__class__

        if fields is None:
            fields = self.get_store_fields()
        # Access check + apply domain filter
        filter = await cls._check_access(Operation.READ, filter=filter)

        session = cls._get_db_session(session)

        stmt, values = cls._builder.build_search(
            fields, start, end, limit, order, sort, filter
        )
        prepare = cls.prepare_list_ids if not raw else None
        records: list[Self] = await session.execute(
            stmt, values, prepare=prepare
        )

        # если есть хоть одна запись и вообще нужно читать поля связей
        fields_relation = [
            (name, field)
            for name, field in cls.get_relation_fields()
            if name in fields
        ]
        if records and fields_relation:
            await cls._records_list_get_relation(
                session, fields_relation, records, fields_nested
            )

        return records

    @hybridmethod
    async def search_count(
        self,
        filter: FilterExpression | None = None,
        session=None,
    ) -> int:
        """
        Count records matching the filter.

        Args:
            filter: Filter expression
            session: Database session

        Returns:
            Number of matching records
        """
        cls = self.__class__
        session = cls._get_db_session(session)

        stmt, values = cls._builder.build_search_count(filter)
        result = await session.execute(stmt, values)

        if result and len(result) > 0:
            return result[0].get("count", 0)
        return 0

    @hybridmethod
    async def exists(
        self,
        filter: FilterExpression | None = None,
        session=None,
    ) -> bool:
        """
        Check if any record matches the filter.

        More efficient than search_count for existence checks.

        Args:
            filter: Filter expression
            session: Database session

        Returns:
            True if at least one record exists
        """
        cls = self.__class__
        session = cls._get_db_session(session)

        stmt, values = cls._builder.build_exists(filter)
        result = await session.execute(stmt, values)

        return bool(result)

    @classmethod
    async def _get_load_relations(
        cls,
        record,
        fields: list[str],
        fields_nested: dict[str, list[str]],
        session,
    ):
        """
        Загрузка relation полей для одной записи.

        Используется из get() когда передан fields_nested.
        Для каждого relation поля выполняет отдельный запрос.

        Формат результата единообразен с search():
            M2O  → объект модели или None
            O2M  → список объектов
            M2M  → список объектов

        Args:
            record: Экземпляр модели с загруженными store полями
            fields: Список запрошенных полей (store + relation)
            fields_nested: Словарь вложенных полей для relations
            session: DB сессия
        """
        fields_relation = [
            (name, field)
            for name, field in cls.get_relation_fields()
            if name in fields
        ]

        if not fields_relation:
            return

        execute_list = []
        request_meta = []  # (field_name, field_type, relation)

        for name, field in fields_relation:
            relation_table = field.relation_table
            relation_table_field = field.relation_table_field

            # Определяем какие поля вложенной модели загружать
            nested = fields_nested.get(name)
            if nested:
                fields_select = nested
            elif relation_table:
                fields_select = ["id"]
                if relation_table.get_fields().get("name"):
                    fields_select.append("name")
                if isinstance(field, PolymorphicMany2one):
                    fields_select = relation_table.get_store_fields_omit_m2o()
            else:
                continue

            if (
                isinstance(field, (Many2one, PolymorphicMany2one))
                and relation_table
            ):
                m2o_id = getattr(record, name)
                if m2o_id is None or isinstance(m2o_id, Field):
                    setattr(record, name, None)
                    continue
                execute_list.append(
                    relation_table.search(
                        fields=fields_select,
                        filter=[("id", "=", m2o_id)],
                        limit=1,
                    )
                )
                request_meta.append((name, "m2o"))

            elif isinstance(field, Many2many) and relation_table:
                execute_list.append(
                    cls.get_many2many(
                        id=record.id,
                        comodel=relation_table,
                        relation=field.many2many_table,
                        column1=field.column1,
                        column2=field.column2,
                        fields=fields_select,
                        limit=None,
                    )
                )
                request_meta.append((name, "m2m"))

            elif (
                isinstance(field, One2many)
                and relation_table
                and relation_table_field
            ):
                execute_list.append(
                    relation_table.search(
                        fields=fields_select,
                        filter=[(relation_table_field, "=", record.id)],
                        limit=1000,
                    )
                )
                request_meta.append((name, "o2m"))

            elif isinstance(field, PolymorphicOne2many) and relation_table:
                execute_list.append(
                    relation_table.search(
                        fields=relation_table.get_store_fields_omit_m2o(),
                        filter=[
                            ("res_id", "=", record.id),
                            ("res_model", "=", record.__table__),
                        ],
                        limit=1000,
                    )
                )
                request_meta.append((name, "o2m"))

            elif (
                isinstance(field, One2one)
                and relation_table
                and relation_table_field
            ):
                execute_list.append(
                    relation_table.search(
                        fields=fields_select,
                        filter=[(relation_table_field, "=", record.id)],
                        limit=1,
                    )
                )
                request_meta.append((name, "m2o"))

        if not execute_list:
            return

        results = await execute_maybe_parallel(execute_list)

        for i, (name, rel_type) in enumerate(request_meta):
            result = results[i]
            if rel_type == "m2o":
                setattr(record, name, result[0] if result else None)
            else:
                # o2m, m2m → список
                setattr(record, name, result if result else [])

    async def _update_relations(
        self, payload: _M, update_fields: list[str], session=None
    ):
        """
        Обновить запись с поддержкой relation полей (M2M, O2M, attachments).

        Вызывается из update() когда fields содержит relation поля.
        Обрабатывает: store поля (через update) + attachments + O2M/M2M.

        Args:
            payload: Экземпляр модели с новыми значениями полей
            update_fields: Список полей для обновления
            session: DB сессия
        """
        session = self._get_db_session(session)

        # Handle attachments
        fields_attachments = [
            (name, field)
            for name, field in self.get_relation_fields_attachment()
            if name in update_fields
        ]

        if fields_attachments:
            for name, field in fields_attachments:
                if isinstance(field, PolymorphicMany2one):
                    field_obj = getattr(payload, name)
                    if field_obj and field.relation_table:
                        # TODO: всегда создавать новую строку аттачмент с файлом
                        # также надо продумать механизм обновления уже существующего файла
                        # надо ли? или проще удалять
                        field_obj["res_id"] = self.id
                        # Оборачиваем dict в объект модели
                        attachment_payload = field.relation_table(**field_obj)
                        attachment_id = await field.relation_table.create(
                            payload=attachment_payload
                        )
                        setattr(payload, name, attachment_id)

        # Update store fields
        fields_store = [
            name for name in self.get_store_fields() if name in update_fields
        ]
        # Обновление сущности в базе без связей
        if fields_store:
            await self._update_store(payload, fields_store, session)

        # защита, оставить только те поля, которые являются отношениями (m2m, o2m)
        # добавлена информаци о вложенных полях
        fields_relation = [
            (name, field)
            for name, field in self.get_relation_fields_m2m_o2m()
            if name in update_fields
        ]

        if fields_relation:
            request_list = []

            for name, field in fields_relation:
                field_obj = getattr(payload, name)

                if isinstance(field, One2one):
                    params = {
                        "limit": 1,
                        "fields": ["id"],
                        "filter": [(field.relation_table_field, "=", self.id)],
                    }
                    record = await field.relation_table.search(**params)
                    if len(record):
                        request_list.append(record[0].update(field_obj))

                if isinstance(field, (One2many, PolymorphicOne2many)):
                    # заменить в связанных полях виртуальный ид на вновь созданный
                    for obj in field_obj.get("created", []):
                        for k, v in obj.items():
                            f = getattr(field.relation_table, k)
                            if (
                                isinstance(f, (Many2one, PolymorphicMany2one))
                                and v == "VirtualId"
                            ):
                                obj[k] = self.id

                    data_created = [
                        field.relation_table(**obj)
                        for obj in field_obj.get("created", [])
                    ]

                    if isinstance(field, PolymorphicOne2many):
                        for obj in data_created:
                            obj.res_id = self.id

                    if field_obj.get("created", []):
                        request_list.append(
                            field.relation_table.create_bulk(data_created)
                        )
                    if field_obj["deleted"]:
                        request_list.append(
                            field.relation_table.delete_bulk(
                                field_obj["deleted"]
                            )
                        )

                if isinstance(field, Many2many):
                    # Replace virtual ID
                    for obj in field_obj.get("created", []):
                        for k, v in obj.items():
                            f = getattr(field.relation_table, k)
                            if (
                                isinstance(f, (Many2one, PolymorphicMany2one))
                                and v == "VirtualId"
                            ):
                                obj[k] = self.id

                    data_created = [
                        field.relation_table(**obj)
                        for obj in field_obj.get("created", [])
                    ]

                    if field_obj.get("created", []):
                        created_ids = await field.relation_table.create_bulk(
                            data_created
                        )
                        if "selected" not in field_obj:
                            field_obj["selected"] = []
                        field_obj["selected"] += [
                            rec["id"] for rec in created_ids
                        ]

                    if field_obj.get("selected"):
                        data_selected = [
                            (self.id, id) for id in field_obj["selected"]
                        ]
                        request_list.append(
                            self.link_many2many(field, data_selected)
                        )

                    if field_obj.get("unselected"):
                        request_list.append(
                            self.unlink_many2many(
                                field, field_obj["unselected"]
                            )
                        )

            for coro in request_list:
                await coro
