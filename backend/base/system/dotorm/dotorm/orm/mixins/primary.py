"""Primary ORM operations mixin."""

from typing import TYPE_CHECKING, Self, TypeVar

from ...access import Operation
from ...components.dialect import POSTGRES
from ...model import JsonMode
from ...decorators import hybridmethod

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
        return await session.execute(stmt, [self.id])

    @hybridmethod
    async def delete_bulk(self, ids: list[int], session=None):
        cls = self.__class__

        # Одна проверка для всех ID
        await cls._check_access(Operation.DELETE, record_ids=ids)

        session = cls._get_db_session(session)
        stmt = cls._builder.build_delete_bulk(len(ids))
        return await session.execute(stmt, ids)

    async def update(
        self,
        payload: "_M | None" = None,
        fields=None,
        session=None,
    ):
        await self._check_access(Operation.UPDATE, record_ids=[self.id])

        session = self._get_db_session(session)
        if payload is None:
            payload = self
        if not fields:
            fields = []

        if fields:
            payload_dict = payload.json(
                include=set(fields),
                exclude_unset=True,
                exclude_none=True,
                only_store=True,
                mode=JsonMode.UPDATE,
            )
        else:
            payload_dict = payload.json(
                exclude=payload.get_none_update_fields_set(),
                exclude_none=True,
                exclude_unset=True,
                only_store=True,
                mode=JsonMode.UPDATE,
            )

        stmt, values = self._builder.build_update(payload_dict, self.id)
        return await session.execute(stmt, values)

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
            exclude_none=True,
            exclude_unset=True,
            only_store=True,
        )

        stmt, values = cls._builder.build_update_bulk(payload_dict, ids)
        return await session.execute(stmt, values)

    @hybridmethod
    async def create(self, payload: _M, session=None) -> int:
        cls = self.__class__

        # Проверяем table access до создания
        await cls._check_access(Operation.CREATE)

        session = cls._get_db_session(session)

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

    @hybridmethod
    async def get(self, id, fields: list[str] = [], session=None) -> Self:
        cls = self.__class__

        await cls._check_access(Operation.READ, record_ids=[id])

        session = cls._get_db_session(session)

        stmt, values = cls._builder.build_get(id, fields)
        record = await session.execute(
            stmt, values, prepare=cls.prepare_form_id
        )

        if not record:
            raise ValueError("Record not found")
        assert isinstance(record, cls)
        return record

    @hybridmethod
    async def table_len(self, session=None) -> int:
        cls = self.__class__
        session = cls._get_db_session(session)
        stmt, values = cls._builder.build_table_len()

        if cls._dialect == POSTGRES:
            prepare = lambda rows: [r["count"] for r in rows]
        else:
            prepare = lambda rows: [r["COUNT(*)"] for r in rows]

        records = await session.execute(stmt, values, prepare=prepare)
        assert records is not None
        if len(records):
            return records[0]
        return 0
