"""Relations ORM operations mixin."""

from typing import TYPE_CHECKING, Any, Literal, Self, TypeVar

from ...components.filter_parser import FilterExpression
from ...decorators import hybridmethod
from ...access import Operation
from ...builder.request_builder import (
    RequestBuilderForm,
)
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
    - get_with_relations - get single record with relations
    - update_with_relations - update record with relations

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
            Для загрузки одной записи по ID с relations можно использовать
            get_with_relations(), но search() эффективнее для множества записей
            благодаря batch-запросам.
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
    async def get_with_relations(
        cls,
        id,
        fields=None,
        fields_info={},
        session=None,
    ) -> Self:
        """
        Получить одну запись по ID с загрузкой relation полей.

        В отличие от search(), выполняет отдельные запросы для каждого relation поля,
        что менее эффективно для множества записей, но удобно для загрузки одной.

        Args:
            id: ID записи для загрузки
            fields: Список полей для загрузки (store + relation).
                   Если не указан - загружаются все store поля.
            fields_info: Словарь с вложенными полями для relation.
                        Например: {"user_id": ["id", "name", "email"]}
            session: DB сессия (опционально)

        Returns:
            Экземпляр модели с загруженными данными

        Raises:
            ValueError: Если запись не найдена

        Example:
            # Загрузить чат с операторами (только id и name)
            chat = await Chat.get_with_relations(
                chat_id,
                fields=["id", "name", "operator_ids"],
                fields_info={"operator_ids": ["id", "name"]}
            )

        Note:
            Для загрузки множества записей с relations лучше использовать
            search() - он выполняет batch-запросы для relations.
        """
        if not fields:
            fields = []
        session = cls._get_db_session(session)

        # защита, оставить только те поля, которые действительно хранятся в базе
        fields_store = [
            name for name in cls.get_store_fields() if name in fields
        ]
        # если вдруг они не заданы, или таких нет, взять все
        if not fields_store:
            fields_store = [name for name in cls.get_store_fields()]
        if "id" not in fields_store:
            fields_store.append("id")

        stmt, values = cls._builder.build_get(id, fields_store)
        record_raw: list[Any] = await session.execute(stmt, values)
        if not record_raw:
            raise ValueError("Record not found")
        record = cls(**record_raw[0])

        # защита, оставить только те поля, которые являются отношениями (m2m, o2m, m2o)
        # добавлена информаци о вложенных полях
        fields_relation = [
            (name, field, fields_info.get(name))
            for name, field in cls.get_relation_fields()
            if name in fields
        ]

        # если есть хоть одна запись и вообще нужно читать поля связей
        if record and fields_relation:
            request_list = []
            execute_list = []

            # добавить запрос на o2m
            for name, field, fields_nested in fields_relation:
                relation_table = field.relation_table
                relation_table_field = field.relation_table_field

                if not fields_nested and relation_table:
                    fields_select = ["id"]
                    if relation_table.get_fields().get("name"):
                        fields_select.append("name")
                    if isinstance(field, PolymorphicMany2one):
                        fields_select = (
                            relation_table.get_store_fields_omit_m2o()
                        )
                else:
                    fields_select = fields_nested

                if (
                    isinstance(field, (Many2one, PolymorphicMany2one))
                    and relation_table
                ):
                    m2o_id = getattr(record, name)
                    stmt, val = relation_table._builder.build_get(
                        m2o_id, fields=fields_select
                    )
                    req = RequestBuilderForm(
                        stmt=stmt,
                        value=val,
                        field_name=name,
                        field=field,
                        fields=fields_select,
                    )
                    request_list.append(req)
                    execute_list.append(
                        session.execute(
                            req.stmt,
                            req.value,
                            prepare=req.function_prepare,
                            cursor=req.function_cursor,
                        )
                    )
                # если m2m или o2m необходимо посчитать длину, для пагинации
                if isinstance(field, Many2many):
                    params = {
                        "id": record.id,
                        "comodel": relation_table,
                        "relation": field.many2many_table,
                        "column1": field.column1,
                        "column2": field.column2,
                        "fields": fields_select,
                        "order": "desc",
                        "start": 0,
                        "end": 40,
                        "sort": "id",
                        "limit": 40,
                    }
                    # records
                    execute_list.append(cls.get_many2many(**params))
                    params["fields"] = ["id"]
                    params["start"] = None
                    params["end"] = None
                    params["limit"] = None
                    # len
                    execute_list.append(cls.get_many2many(**params))
                    req = RequestBuilderForm(
                        stmt=None,
                        value=None,
                        field_name=name,
                        field=field,
                        fields=fields_select,
                    )
                    request_list.append(req)

                if isinstance(field, One2many) and relation_table:
                    params = {
                        "start": 0,
                        "end": 40,
                        "limit": 40,
                        "fields": fields_select,
                        "filter": [(relation_table_field, "=", record.id)],
                    }
                    execute_list.append(relation_table.search(**params))
                    params["fields"] = ["id"]
                    params["start"] = None
                    params["end"] = None
                    params["limit"] = 1000
                    execute_list.append(relation_table.search(**params))
                    req = RequestBuilderForm(
                        stmt=None,
                        value=None,
                        field_name=name,
                        field=field,
                        fields=fields_select,
                    )
                    request_list.append(req)

                if isinstance(field, PolymorphicOne2many) and relation_table:
                    params = {
                        "start": 0,
                        "end": 40,
                        "limit": 40,
                        "fields": relation_table.get_store_fields_omit_m2o(),
                        "filter": [
                            ("res_id", "=", record.id),
                            ("res_model", "=", record.__table__),
                        ],
                    }
                    execute_list.append(relation_table.search(**params))
                    params["fields"] = ["id"]
                    params["start"] = None
                    params["end"] = None
                    params["limit"] = 1000
                    execute_list.append(relation_table.search(**params))
                    req = RequestBuilderForm(
                        stmt=None,
                        value=None,
                        field_name=name,
                        field=field,
                        fields=relation_table.get_store_fields_omit_m2o(),
                    )
                    request_list.append(req)

                if isinstance(field, One2one) and relation_table:
                    params = {
                        "limit": 1,
                        "fields": fields_select,
                        "filter": [(relation_table_field, "=", record.id)],
                    }
                    execute_list.append(relation_table.search(**params))
                    req = RequestBuilderForm(
                        stmt=None,
                        value=None,
                        field_name=name,
                        field=field,
                        fields=fields_select,
                    )
                    request_list.append(req)

            # выполняем последовательно в транзакции, параллельно вне транзакции
            results = await execute_maybe_parallel(execute_list)

            # добавляем атрибуты к исходному объекту,
            # получая удобное обращение через дот-нотацию
            i = 0
            for request_builder in request_list:
                result = results[i]

                if isinstance(
                    request_builder.field,
                    (Many2one, PolymorphicMany2one, One2one),
                ):
                    # m2o нужно распаковать так как он тоже в списке
                    # если пустой список, то установить None
                    result = result[0] if result else None

                if isinstance(
                    request_builder.field,
                    (Many2many, One2many, PolymorphicOne2many),
                ):
                    # если m2m или o2m необбзодимо взять два результатата
                    # так как один из них это число всех строк таблицы
                    # для пагинации
                    fields_info = request_builder.field.relation_table.get_fields_info_list(
                        request_builder.fields
                    )
                    result = {
                        "data": result,
                        "fields": fields_info,
                        "total": len(results[i + 1]),
                    }
                    i += 1

                setattr(record, request_builder.field_name, result)
                i += 1

        return record

    async def update_with_relations(
        self, payload: _M, update_fields: list[str] | None = None, session=None
    ):
        """
        Обновить запись с поддержкой relation полей (M2M, O2M, attachments).

        Args:
            payload: Экземпляр модели с новыми значениями полей
            update_fields: Список полей для обновления.
                          Если None - автоматически определяются из payload
                          (все поля которые не являются Field и не id).
            session: DB сессия (опционально)

        Returns:
            Результат обновления store полей

        Example:
            # Автоопределение полей из payload
            user.name = "New Name"
            user.email = "new@email.com"
            await user.update_with_relations(user)

            # Явное указание полей
            await user.update_with_relations(payload, update_fields=["name", "role_ids"])
        """
        session = self._get_db_session(session)

        # Автоопределение полей если не указаны явно
        if update_fields is None:
            update_fields = [
                name
                for name, field_class in payload.get_fields().items()
                if not isinstance(getattr(payload, name), Field)
                and name != "id"
            ]

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

        # Update stored fields
        fields_store = [
            name for name in self.get_store_fields() if name in update_fields
        ]
        # Обновление сущности в базе без связей
        if fields_store:
            await self.update(payload, update_fields, session)

        # защита, оставить только те поля, которые являются отношениями (m2m, o2m)
        # добавлена информаци о вложенных полях
        fields_relation = [
            (name, field)
            for name, field in self.get_relation_fields_m2m_o2m()
            if name in update_fields
        ]

        if fields_relation:
            request_list = []
            field_list = []

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
                    field_list.append(field)
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
                    field_list.append(field)

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

            # выполняем последовательно
            await execute_maybe_parallel(request_list)

        # return record_raw
