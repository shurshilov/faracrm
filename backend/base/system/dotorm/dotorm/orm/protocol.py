"""Protocols defining what ORM mixins expect from the model class."""

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
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
    from ..model import FieldKind
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
    __indexes__: ClassVar[list[tuple[str, ...]]]
    _pool: ClassVar[Union["aiomysql.Pool", "asyncpg.Pool"]]
    _no_transaction: ClassVar[Type]
    _dialect: ClassVar["Dialect"]
    _builder: ClassVar["Builder"]

    # Кэши модели — тот же список, что в DotModel (model.py), держать в
    # синхроне; заполняют _build_field_cache / _build_compute_cache /
    # _build_constrains_cache / _build_onchange_cache, миксины читают их
    # через cls.
    _cache_all_fields: ClassVar[dict[str, "Field"]]
    _cache_store_fields_dict: ClassVar[dict[str, "Field"]]
    _cache_public_fields: ClassVar[dict[str, "Field"]]
    _cache_relation_fields: ClassVar[list[tuple[str, "Field"]]]
    _cache_json_fields: ClassVar[list[str]]
    _cache_compute_fields: ClassVar[list[tuple[str, Callable]]]
    _cache_all_field_kinds: ClassVar[dict[str, "FieldKind"]]
    _cache_default_plan: ClassVar[list]
    _cache_compute_method_deps: ClassVar[dict[str, tuple[str, ...]]]
    _cache_compute_prefetch_deps: ClassVar[dict[str, tuple[str, ...]]]
    _cache_compute_writes: ClassVar[dict[str, set[str]]]
    _cache_compute_by_dep: ClassVar[dict[str, set[str]]]
    _cache_constrains: ClassVar[tuple[tuple[str, frozenset[str]], ...]]
    _cache_onchange: ClassVar[dict[str, list[str]]]

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

    @classmethod
    async def _check_field_access(
        cls,
        operation: "Operation",
        fields: Any,
        filter: list | None = None,
        sort: str | None = None,
    ) -> list[str]: ...

    # @constrains (from OrmPrimaryMixin)
    @classmethod
    async def _run_constrains(
        cls, records: list[Any], changed: Any
    ) -> None: ...

    # Field introspection
    @classmethod
    def get_fields(cls) -> dict[str, "Field"]: ...

    @classmethod
    def get_store_fields(cls) -> list[str]: ...

    @classmethod
    def get_store_fields_dict(cls) -> dict[str, "Field"]: ...

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
        depends_jobs: Any = None,
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
        limit: int | None = None,
        session: Any = None,
        filter: list | None = None,
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
        owner_id: int | list[int],
        session: Any = None,
    ) -> Any: ...

    @classmethod
    async def _records_list_get_relation(
        cls,
        session: Any,
        fields_relation: list[tuple[str, "Field"]],
        records: list[Any],
        fields_nested: dict[str, dict] | None = None,
    ) -> None: ...

    # From OrmRelationsMixin
    @classmethod
    async def _get_load_relations(
        cls,
        record: Any,
        fields: list[str],
        fields_nested: dict[str, dict],
        session: Any,
    ) -> None: ...

    async def _update_relations(
        self,
        payload: Any,
        update_fields: list[str],
        session: Any,
        depends_jobs: Any = None,
        ids: list[int] | None = None,
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
