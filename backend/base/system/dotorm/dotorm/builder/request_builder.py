"""Request builder for relation queries."""

from __future__ import annotations
from dataclasses import dataclass, field as d_field
from typing import Any, Callable, ClassVar
from enum import Enum, auto

from ..fields import (
    PolymorphicMany2one,
    PolymorphicOne2many,
    Field,
    Many2many,
    Many2one,
    One2many,
)


class FetchMode(Enum):
    """Database cursor fetch mode."""

    FETCHALL = auto()
    FETCHONE = auto()
    FETCHMANY = auto()


# Type aliases for relation fields
RelationField = Many2many | One2many | Many2one
FormRelationField = (
    Many2many | One2many | Many2one | PolymorphicMany2one | PolymorphicOne2many
)


@dataclass(slots=True)
class RequestBuilder:
    """
    Container for relation query request.

    Immutable data container with computed properties for
    determining how to process query results.
    """

    stmt: str | None
    value: Any
    field_name: str
    field: Field
    fields: list[str] = d_field(default_factory=lambda: ["id", "name"])
    fetch_mode: FetchMode = FetchMode.FETCHALL

    # Mapping for prepare functions based on field type
    _PREPARE_FUNCS: ClassVar[dict[type, str]] = {
        Many2many: "prepare_list_ids",
        One2many: "prepare_list_ids",
        Many2one: "prepare_list_ids",
        PolymorphicMany2one: "prepare_list_ids",
        PolymorphicOne2many: "prepare_list_ids",
    }

    @property
    def function_cursor(self) -> str:
        """Returns cursor method name based on fetch mode."""
        return self.fetch_mode.name.lower()

    @property
    def function_prepare(self) -> Callable:
        """
        Returns appropriate prepare function based on field type.

        For relation fields (Many2many, One2many, Many2one),
        returns prepare_list_ids from relation_table.
        """
        for field_type, method_name in self._PREPARE_FUNCS.items():
            if isinstance(self.field, field_type):
                return getattr(self.field.relation_table, method_name)

        # Fallback for non-relation fields
        # TODO: помоему тут ошибка relation_table всегда будет пустое
        # а реквест билдер всеравно не используется в не связей
        # и else никогда не вызывается
        return getattr(self.field.relation_table, "prepare_list_id")


@dataclass(slots=True)
class RequestBuilderForm(RequestBuilder):
    """
    Container for form relation query request.

    Extends RequestBuilder with form-specific prepare functions.
    """

    # Override mapping for form context
    _PREPARE_FUNCS: ClassVar[dict[type, str]] = {
        Many2many: "prepare_form_ids",
        One2many: "prepare_form_ids",
        Many2one: "prepare_form_ids",
        PolymorphicMany2one: "prepare_form_ids",
        PolymorphicOne2many: "prepare_form_ids",
    }

    @property
    def function_prepare(self) -> Callable:
        """
        Returns appropriate prepare function for form context.

        Form context uses prepare_form_ids/prepare_form_id methods.
        """
        for field_type, method_name in self._PREPARE_FUNCS.items():
            if isinstance(self.field, field_type):
                return getattr(self.field.relation_table, method_name)

        return getattr(self.field.relation_table, "prepare_form_id")


def create_request_builder(
    stmt: str | None,
    value: Any,
    field_name: str,
    field: Field,
    fields: list[str] | None = None,
    *,
    form_mode: bool = False,
) -> RequestBuilder:
    """
    Factory function for creating appropriate RequestBuilder.

    Args:
        stmt: SQL statement
        value: Query parameters
        field_name: Name of the field
        field: Field instance
        fields: Fields to select (default: ["id", "name"])
        form_mode: If True, creates RequestBuilderForm

    Returns:
        RequestBuilder or RequestBuilderForm instance
    """
    if fields is None:
        fields = ["id", "name"]

    cls = RequestBuilderForm if form_mode else RequestBuilder
    return cls(
        stmt=stmt,
        value=value,
        field_name=field_name,
        field=field,
        fields=fields,
    )
