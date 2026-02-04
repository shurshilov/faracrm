"""Protocols defining what ORM mixins expect from the model class."""

from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Protocol,
    Self,
    Type,
    Union,
    runtime_checkable,
)

if TYPE_CHECKING:
    from ..builder.builder import Builder
    from ..components.dialect import Dialect
    from ..fields import Field
    from ..access import Operation
    import aiomysql
    import asyncpg


@runtime_checkable
class DotModelProtocol(Protocol):
    """
    Base protocol that all ORM mixins expect.

    Defines the full interface that DotModel provides.
    All mixins inherit from this protocol for type checking.
    """

    __table__: ClassVar[str]
    __auto_create__: ClassVar[bool] = True
    _pool: ClassVar[Union["aiomysql.Pool", "asyncpg.Pool"]]
    _no_transaction: ClassVar[Type]
    _dialect: ClassVar["Dialect"]
    _builder: ClassVar["Builder"]

    id: int

    # Session
    @classmethod
    def _get_db_session(cls, session=None) -> Any: ...

    # Access control (from AccessMixin)
    @classmethod
    async def _check_access(
        cls,
        operation: "Operation",
        record_ids: list[int] | None = None,
        filter: list | None = None,
    ) -> list | None: ...

    # Field introspection
    @classmethod
    def get_fields(cls) -> dict[str, "Field"]: ...

    @classmethod
    def get_store_fields(cls) -> list[str]: ...

    @classmethod
    def get_store_fields_omit_m2o(cls) -> list[str]: ...

    @classmethod
    def get_relation_fields(cls) -> list[tuple[str, "Field"]]: ...

    @classmethod
    def get_relation_fields_m2m_o2m(cls) -> list[tuple[str, "Field"]]: ...

    @classmethod
    def get_relation_fields_attachment(cls) -> list[tuple[str, "Field"]]: ...

    # Serialization
    @classmethod
    def prepare_list_ids(cls, rows: list[dict]) -> list[Self]: ...

    @classmethod
    def prepare_form_id(cls, r: list) -> Self | None: ...

    def json(
        self,
        include: Any = ...,
        exclude: Any = ...,
        exclude_none: bool = ...,
        exclude_unset: bool = ...,
        only_store: Any = ...,
        mode: Any = ...,
    ) -> dict[str, Any]: ...

    @classmethod
    def get_none_update_fields_set(cls) -> set[str]: ...

    def __init__(self, **kwargs: Any) -> None: ...

    # From OrmPrimaryMixin
    async def update(
        self,
        payload: Self,
        fields: Any = None,
        session: Any = None,
    ) -> Any: ...

    # From OrmMany2manyMixin
    @classmethod
    async def get_many2many(
        cls,
        id: int,
        comodel: Any,
        relation: str,
        column1: str,
        column2: str,
        fields: list[str] | None = None,
        order: str = "desc",
        start: int | None = None,
        end: int | None = None,
        sort: str = "id",
        limit: int | None = 10,
        session: Any = None,
    ) -> list[Any]: ...

    @classmethod
    async def link_many2many(
        cls,
        field: Any,
        values: list,
        session: Any = None,
    ) -> Any: ...

    @classmethod
    async def unlink_many2many(
        cls,
        field: Any,
        ids: list,
        session: Any = None,
    ) -> Any: ...

    @classmethod
    async def _records_list_get_relation(
        cls,
        session: Any,
        fields_relation: list[tuple[str, "Field"]],
        records: list[Any],
        fields_nested: dict[str, list[str]] | None = None,
    ) -> None: ...

    # From OrmRelationsMixin
    @classmethod
    async def _get_load_relations(
        cls,
        record: Any,
        fields: list[str],
        fields_nested: dict[str, list[str]],
        session: Any,
    ) -> None: ...

    async def _update_relations(
        self,
        payload: Any,
        update_fields: list[str],
        session: Any,
    ) -> None: ...

    async def _update_store(
        self,
        payload: Any,
        fields: list[str],
        session: Any,
    ) -> Any: ...

    # From DDLMixin
    @staticmethod
    def format_default_value(value: Any) -> str: ...
