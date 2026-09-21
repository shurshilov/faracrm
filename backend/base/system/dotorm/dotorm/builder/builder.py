"""
SQL Query Builder.

Combines base state with mixin functionality.
"""

from typing import TYPE_CHECKING

from ..components.filter_parser import FilterParser

from .mixins import (
    CRUDMixin,
    Many2ManyMixin,
    RelationsMixin,
)

if TYPE_CHECKING:
    from ..fields import Field
    from ..components.dialect import Dialect


class Builder(
    CRUDMixin,
    Many2ManyMixin,
    RelationsMixin,
):
    """
    Unified SQL query builder.

    Inherits from:
        - CRUDMixin: create, read, update, delete operations
        - Many2ManyMixin: M2M relation queries
        - RelationsMixin: Batch relation loading

    Example:
        builder = Builder(
            table="users",
            fields=model_fields,
            dialect=POSTGRES,
        )

        # Simple queries
        sql, vals = builder.build_get(id=1)
        sql, vals = builder.build_delete(id=1)

        # Search with filter
        sql, vals = builder.build_search(
            fields=["id", "name"],
            filter=[("status", "=", "active")],
            limit=10,
        )

    MRO ensures BuilderBase.__init__ is called and provides
    all attributes that mixins expect.
    """

    __slots__ = ("table", "fields", "dialect", "filter_parser", "store_fields")

    def __init__(
        self,
        table: str,
        fields: dict[str, "Field"],
        dialect: "Dialect",
    ) -> None:
        self.table = table
        self.fields = fields
        self.dialect = dialect
        self.filter_parser = FilterParser(dialect, fields)
        # Один раз на билдер, а не на каждый build_*: билдер пересоздаётся
        # вместе с кэшами модели (rebuild_field_caches), не устареет.
        self.store_fields = [
            name for name, field in fields.items() if field.store
        ]

    def get_store_fields(self) -> list[str]:
        """Field names stored in DB (store=True), precomputed in __init__."""
        return self.store_fields
