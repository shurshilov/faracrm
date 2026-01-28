"""Protocol defining what mixins expect from the base class."""

from typing import TYPE_CHECKING, Literal, Protocol, Type, runtime_checkable

from ..components.filter_parser import FilterExpression

if TYPE_CHECKING:
    from ..model import DotModel
    from ..fields import Field
    from ..components.dialect import Dialect
    from ..components.filter_parser import FilterParser


@runtime_checkable
class BuilderProtocol(Protocol):
    """Contract that mixins expect from the base class."""

    table: str
    fields: dict[str, "Field"]
    dialect: "Dialect"
    filter_parser: "FilterParser"

    def get_store_fields(self) -> list[str]:
        """Returns field names that are stored in DB."""
        ...

    def build_search(
        self,
        fields: list[str] | None = None,
        start: int | None = None,
        end: int | None = None,
        limit: int = 80,
        order: Literal["DESC", "ASC", "desc", "asc"] = "DESC",
        sort: str = "id",
        filter: FilterExpression | None = None,
        raw: bool = False,
    ) -> tuple[str, tuple]: ...

    def build_get_many2many_multiple(
        self: "BuilderProtocol",
        ids: list[int],
        relation_table: Type["DotModel"],
        many2many_table: str,
        column1: str,
        column2: str,
        fields: list[str] | None = None,
        limit: int = 80,
    ) -> tuple[str, tuple]: ...

    def build_get_many2many(
        self,
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
        limit: int | None = 10,
    ) -> tuple[str, tuple]: ...
