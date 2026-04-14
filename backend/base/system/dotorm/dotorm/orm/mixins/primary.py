"""Primary ORM operations mixin."""

import asyncio
import json
from typing import TYPE_CHECKING, Self, TypeVar

from ...exceptions import RecordNotFound
from ...fields import Field
from ...access import Operation
from ...components.dialect import POSTGRES
from ...model import JsonMode
from ...decorators import hybridmethod
from ...fields import TranslatedChar

if TYPE_CHECKING:
    from ..protocol import DotModelProtocol
    from ...model import DotModel

    _Base = DotModelProtocol
else:
    _Base = object


# TypeVar for generic payload - accepts any DotModel subclass
_M = TypeVar("_M", bound="DotModel")


class OrmPrimaryMixin(_Base):
    """
    Mixin providing primary CRUD ORM operations.

    Provides:
    - create, create_bulk
    - get, table_len
    - update, update_bulk
    - delete, delete_bulk

    Expects DotModel to provide:
    - _get_db_session()
    - _builder
    - _dialect
    - __table__
    - prepare_form_id()
    """

    async def delete(self, session=None):
        await self._check_access(Operation.DELETE, record_ids=[self.id])

        session = self._get_db_session(session)
        stmt = self._builder.build_delete()
        return await session.execute(stmt, [self.id], cursor="void")

    @hybridmethod
    async def delete_bulk(self, ids: list[int], session=None):
        cls = self.__class__

        # Одна проверка для всех ID
        await cls._check_access(Operation.DELETE, record_ids=ids)

        session = cls._get_db_session(session)
        stmt = cls._builder.build_delete_bulk(len(ids))

        if cls._dialect.name == "postgres":
            # ANY($1::int[]) — ids as single array param
            return await session.execute(stmt, [ids], cursor="void")

        # IN (%s, %s, ...) — ids as individual params
        return await session.execute(stmt, ids, cursor="void")

    async def update(
        self,
        payload: "_M",
        fields: list[str] | None = None,
        session=None,
    ):
        """
        Обновить запись.

        Автоматически обрабатывает и store поля (SQL UPDATE),
        и relation поля (O2M/M2M: created/deleted/selected/unselected,
        attachments: PolymorphicMany2one).

        После обновления БД store-поля из payload синхронизируются в self.

        Args:
            payload: Данные для обновления (экземпляр модели).
            fields: Список полей для обновления.
                    Если None — обновляются все заданные поля из payload.
            session: DB сессия

        Example:
            # Store поля
            await record.update(User(name="New", email="new@test.com"))

            # Store + relations
            await record.update(User(name="New", role_ids={"selected": [1, 2]}))

            # Конкретные поля
            await record.update(payload, fields=["name", "email"])
        """
        await self._check_access(Operation.UPDATE, record_ids=[self.id])

        session = self._get_db_session(session)

        # Автоопределение полей если не указаны
        if not fields:
            fields = [
                name
                for name, field_class in payload.get_fields().items()
                if not isinstance(getattr(payload, name), Field)
                and name != "id"
            ]

        if not fields:
            return

        await self._update_relations(payload, fields, session)

        # Синхронизировать self с payload после успешного обновления
        if payload is not self:
            self._sync_after_update(payload, fields)

    def _sync_after_update(self, payload: "_M", fields: list[str]):
        """
        Синхронизировать self с payload после успешного update.

        Копируем только store-поля (скаляры, M2O FK) из payload в self.
        Relation-поля (O2M, M2M) не синхронизируются — в payload они
        в формате команд {created/deleted/selected/unselected},
        а на self — список объектов. Если нужны актуальные relations
        после update — следует перечитать запись из БД.

        Аналогично другим ORM:
        - SQLAlchemy: expire + lazy reload при обращении (доп. SELECT)
        - Django: self уже мутирован до save(), M2M — отдельные операции
        - Tortoise: self уже мутирован до save(), M2M — отдельные операции
        """
        store_fields = set(self.get_store_fields())
        for name in fields:
            if name in store_fields:
                setattr(self, name, getattr(payload, name))

    async def _update_store(
        self,
        payload: "_M",
        fields: list[str],
        session,
    ):
        """Прямой SQL UPDATE для store полей. Без access check и relations."""
        payload_dict = payload.json(
            include=set(fields),
            exclude_unset=True,
            exclude_none=True,
            only_store=True,
            mode=JsonMode.UPDATE,
        )
        if payload_dict:
            stmt, values = self._builder.build_update(payload_dict, self.id)
            return await session.execute(stmt, values, cursor="void")

    @hybridmethod
    async def update_bulk(
        self,
        ids: list[int],
        payload: _M,
        session=None,
    ):
        cls = self.__class__

        # Одна проверка для всех ID
        await cls._check_access(Operation.UPDATE, record_ids=ids)

        session = cls._get_db_session(session)

        payload_dict = payload.json(
            exclude=payload.get_none_update_fields_set(),
            # exclude_none=True,
            exclude_unset=True,
            only_store=True,
        )

        stmt, values = cls._builder.build_update_bulk(payload_dict, ids)
        return await session.execute(stmt, values, cursor="void")

    @hybridmethod
    async def create(self, payload: _M, session=None) -> int:
        cls = self.__class__

        # Проверяем table access до создания
        await cls._check_access(Operation.CREATE)

        session = cls._get_db_session(session)

        # Применяем default-ы к незаданным store-полям ДО сериализации.
        # json() только сериализует — он не вычисляет дефолты.
        await cls._apply_defaults(payload)

        payload_dict = payload.json(
            exclude=payload.get_none_update_fields_set(),
            exclude_none=True,
            only_store=True,
            mode=JsonMode.CREATE,
        )

        stmt, values = cls._builder.build_create(payload_dict)

        if cls._dialect.supports_returning:
            stmt += " RETURNING id"
            record = await session.execute(stmt, values, cursor="fetch")
            assert record is not None
            record_id = record[0]["id"]
        else:
            record = await session.execute(stmt, values, cursor="lastrowid")
            assert record is not None
            record_id = record

        # Проверяем row access после создания (для Rules типа "только свои записи")
        await cls._check_access(Operation.CREATE, record_ids=[record_id])

        return record_id

    def _check_translated_field(self, field_name):
        """Проверяет что поле существует и это TranslatedChar. Возвращает field."""

        field = self.__class__._cache_all_fields.get(field_name)
        if not isinstance(field, TranslatedChar):
            raise TypeError(
                f"{self.__class__.__name__}.{field_name} is not TranslatedChar"
            )
        return field

    @hybridmethod
    async def get_field_translations(
        self, field_name: str, session=None
    ) -> dict:
        """Возвращает все переводы TranslatedChar поля (обходит deserialization)."""

        self._check_translated_field(field_name)
        await self.__class__._check_access(
            Operation.READ, record_ids=[self.id]
        )
        session = self.__class__._get_db_session(session)
        stmt = f'SELECT "{field_name}" FROM "{self.__class__.__table__}" WHERE id = $1'
        rows = await session.execute(stmt, [self.id], cursor="fetch")
        if not rows:
            return {}
        raw = rows[0][field_name]
        return json.loads(raw) if isinstance(raw, str) and raw else (raw or {})

    @hybridmethod
    async def update_field_translations(
        self, field_name: str, translations: dict, session=None
    ) -> None:
        """Merge-обновление переводов TranslatedChar поля в БД."""

        self._check_translated_field(field_name)
        current = await self.get_field_translations(
            field_name, session=session
        )
        merged = {**current, **translations}
        await self.__class__._check_access(
            Operation.UPDATE, record_ids=[self.id]
        )
        session = self.__class__._get_db_session(session)
        stmt = f'UPDATE "{self.__class__.__table__}" SET "{field_name}" = $1 WHERE id = $2'
        await session.execute(
            stmt,
            [json.dumps(merged, ensure_ascii=False), self.id],
            cursor="void",
        )

    @hybridmethod
    async def create_bulk(self, payload: list[_M], session=None):
        cls = self.__class__

        # Проверяем table access до создания
        await cls._check_access(Operation.CREATE)

        session = cls._get_db_session(session)

        exclude_fields = {
            name
            for name, field in cls.get_fields().items()
            if field.primary_key
        }

        for p in payload:
            await cls._apply_defaults(p)

        payloads_dicts = [
            p.json(
                exclude=exclude_fields, only_store=True, mode=JsonMode.CREATE
            )
            for p in payload
        ]

        stmt, values = cls._builder.build_create_bulk(payloads_dicts)

        if cls._dialect.supports_returning:
            stmt += " RETURNING id"

        records = await session.execute(stmt, values, cursor="fetch")

        # Проверяем row access после создания
        if records:
            created_ids = [r["id"] for r in records]
            await cls._check_access(Operation.CREATE, record_ids=created_ids)

        return records

    @staticmethod
    async def _apply_defaults(payload: "DotModel") -> None:
        """
        Применить default-значения к незаданным store-полям payload.

        Вызывается из create()/create_bulk() ПЕРЕД сериализацией.
        Разделение ответственности (как в SQLAlchemy/Django):
        - default вычисляется при INSERT, не при сериализации
        - json() только отдаёт то, что есть в объекте
        - async callable defaults поддерживаются (await)

        Args:
            payload: Экземпляр модели с данными для создания записи.
                     Незаданные поля остаются как Field дескрипторы.
        """

        for field_name, field_class in payload.get_store_fields_dict().items():
            value = getattr(payload, field_name)
            if isinstance(value, Field) and field_class.default is not None:
                if callable(field_class.default):
                    if asyncio.iscoroutinefunction(field_class.default):
                        setattr(
                            payload, field_name, await field_class.default()
                        )
                    else:
                        setattr(payload, field_name, field_class.default())
                else:
                    setattr(payload, field_name, field_class.default)

    @hybridmethod
    async def get(
        self,
        id,
        fields: list[str] | None = None,
        fields_nested: dict[str, list[str]] | None = None,
        session=None,
    ) -> Self:
        """
        Получить запись по ID.

        Args:
            id: ID записи
            fields: Список полей для загрузки (store + relation).
            fields_nested: Словарь вложенных полей для relation.
                Если передан — relation поля из fields загружаются:
                    M2O  → объект модели или None
                    O2M  → список объектов []
                    M2M  → список объектов []
                Если не передан — только store поля (M2O = integer FK).
                Пример: {"user_id": ["id", "name"], "tag_ids": ["id", "name"]}
            session: DB сессия

        Returns:
            Экземпляр модели

        Raises:
            RecordNotFound: Если запись не найдена

        Example:
            # Только store поля
            chat = await Chat.get(5)
            chat.user_id  # → 42 (int)

            # С relations
            chat = await Chat.get(5,
                fields=["id", "name", "user_id", "message_ids"],
                fields_nested={"user_id": ["id", "name"]}
            )
            chat.user_id  # → User(id=42, name="John")
        """

        cls = self.__class__
        record = await cls.get_or_none(id, fields, fields_nested, session)

        if record is None:
            raise RecordNotFound(cls.__name__, id)

        return record

    @hybridmethod
    async def get_or_none(
        self,
        id,
        fields: list[str] | None = None,
        fields_nested: dict[str, list[str]] | None = None,
        session=None,
    ) -> Self | None:
        """
        Получить запись по ID или None если не найдена.

        Используйте когда отсутствие записи — нормальная ситуация
        (проверка существования, опциональные связи).

        Args:
            id: ID записи
            fields: Список полей для загрузки
            fields_nested: Словарь вложенных полей для relation
            session: DB сессия

        Returns:
            Экземпляр модели или None

        Example:
            # Проверка существования
            user = await User.get_or_none(user_id)
            if user is None:
                return {"error": "User not found"}
        """
        cls = self.__class__

        await cls._check_access(Operation.READ, record_ids=[id])

        session = cls._get_db_session(session)

        # Фильтруем fields — оставляем только store поля для SQL
        store_fields = cls.get_store_fields()
        fields_store = (
            [f for f in (fields or []) if f in store_fields] if fields else []
        )
        if not fields_store:
            fields_store = list(store_fields)
        if "id" not in fields_store:
            fields_store.append("id")

        stmt, values = cls._builder.build_get(id, fields_store)
        record = await session.execute(
            stmt, values, prepare=cls.prepare_form_id
        )

        if not record:
            return None

        assert isinstance(record, cls)

        # Загрузка relations если передан fields_nested
        if fields_nested is not None and fields:
            await cls._get_load_relations(
                record, fields, fields_nested, session
            )

        return record

    @hybridmethod
    async def table_len(self, session=None) -> int:
        """Return total number of records in the table."""
        cls = self.__class__
        session = cls._get_db_session(session)
        stmt, values = cls._builder.build_table_len()

        def _prepare_postgres(rows):
            return [r["count"] for r in rows]

        def _prepare_other(rows):
            return [r["COUNT(*)"] for r in rows]

        prepare = (
            _prepare_postgres if cls._dialect == POSTGRES else _prepare_other
        )

        records = await session.execute(stmt, values, prepare=prepare)
        assert records is not None
        if len(records):
            return records[0]
        return 0
