"""
ModelsCore._attach_polymorphic_fields: поля-связи на полиморфных детей
(activity_ids, attachment_ids) навешиваются на каждую модель одним
add_fields — одна пересборка кэшей на модель, а не на каждого ребёнка.

No database.
"""

import pytest

from backend.base.system.core.models import ModelsCore
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    PolymorphicOne2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel

pytestmark = pytest.mark.unit


class Activity(DotModel):
    __table__ = "t_poly_activity"
    __polymorphic_field__ = ("activity_ids", [("active", "=", True)])

    id: int = Integer(primary_key=True)
    res_model: str | None = Char()
    res_id: int | None = Integer()


class Attachment(DotModel):
    __table__ = "t_poly_attachment"
    __polymorphic_field__ = ("attachment_ids", None)

    id: int = Integer(primary_key=True)
    res_model: str | None = Char()
    res_id: int | None = Integer()


class Lead(DotModel):
    __table__ = "t_poly_lead"

    id: int = Integer(primary_key=True)
    name: str | None = Char()


class Models(ModelsCore):
    activity = Activity
    attachment = Attachment
    lead = Lead


def _registered() -> Models:
    """Как после _build_table_mapping, но словари — на экземпляре, чтобы не
    трогать общие class-level словари ModelsCore."""
    models = Models()
    models._table_to_model_name = {}
    models._table_to_model_class = {}
    for name in ("activity", "attachment", "lead"):
        cls = getattr(models, name)
        models._table_to_model_name[cls.__table__] = name
        models._table_to_model_class[cls.__table__] = cls
    return models


def _count_rebuilds(monkeypatch, cls, calls: list[str]) -> None:
    original = cls.rebuild_field_caches

    def counting():
        calls.append(cls.__name__)
        original()

    monkeypatch.setattr(cls, "rebuild_field_caches", counting)


def test_fields_attached_with_one_rebuild_per_model(monkeypatch):
    models = _registered()
    calls: list[str] = []
    for cls in (Activity, Attachment, Lead):
        _count_rebuilds(monkeypatch, cls, calls)

    models._attach_polymorphic_fields()

    # два поля на Lead — одна пересборка; дети поля не получают вовсе
    assert calls == ["Lead"]
    assert isinstance(Lead.get_fields()["activity_ids"], PolymorphicOne2many)
    assert isinstance(Lead.get_fields()["attachment_ids"], PolymorphicOne2many)
    assert Lead.activity_ids.relation_table is Activity
    assert Lead.activity_ids.filter == [("active", "=", True)]
    assert Lead.attachment_ids.filter is None
    assert "activity_ids" in Lead._builder.fields
    assert "activity_ids" not in Activity.get_fields()
    assert "attachment_ids" not in Attachment.get_fields()
