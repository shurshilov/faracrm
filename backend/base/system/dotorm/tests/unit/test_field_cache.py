"""
Unit-тесты кэшей класса DotModel (model.py: _build_field_cache и компания).

Контракт (аудит кэшей 2026-09-20):
- store=False поле с compute="имя_метода" считается в __init__ так же, как
  compute=callable: метод резолвится один раз при определении класса,
  опечатка в имени — ошибка при определении, а не на каждой строке;
- изменяемый default (list/dict/set) store-поля копируется на каждую
  запись — payload'ы не делят один объект класса;
- add_fields добавляет несколько полей одной пересборкой кэшей и билдера;
- get_store_fields отдаёт список, независимый от кэша;
- список кэшей DotModel и DotModelProtocol совпадает.

No database.
"""

import pytest

from dotorm.fields import Char, Integer, JSONField
from dotorm.model import DotModel
from dotorm.orm.protocol import DotModelProtocol

pytestmark = pytest.mark.unit


class Item(DotModel):
    __table__ = "t_cache_item"

    id: int = Integer(primary_key=True)
    name: str | None = Char()
    status: str = Char(default="draft")
    settings: dict | None = JSONField(default={})
    tags: list | None = JSONField(default=[])
    label: str | None = Char(store=False, compute="_compute_label")
    double: int | None = Integer(
        store=False, compute=lambda rec: (rec.id or 0) * 2
    )

    def _compute_label(self):
        return f"#{self.id}"


class TestNonStoreCompute:
    def test_method_name_resolved(self):
        assert Item(id=7).label == "#7"

    def test_callable(self):
        assert Item(id=4).double == 8

    def test_slow_path_prepare_list_ids(self):
        rows = Item.prepare_list_ids([{"id": 1, "name": "a"}, {"id": 2}])

        assert [row.label for row in rows] == ["#1", "#2"]

    def test_unknown_method_fails_at_class_definition(self):
        with pytest.raises(AttributeError):

            class Broken(DotModel):
                __table__ = "t_cache_broken"

                id: int = Integer(primary_key=True)
                x: int | None = Integer(store=False, compute="_no_such_method")


class TestMutableDefault:
    async def test_each_record_gets_own_copy(self):
        a, b = Item(), Item()
        await Item._apply_defaults(a)
        await Item._apply_defaults(b)

        a.settings["x"] = 1
        a.tags.append("t")

        assert b.settings == {}
        assert b.tags == []
        # дефолт самого класса тоже не тронут
        assert Item.get_fields()["settings"].default == {}
        assert Item.get_fields()["tags"].default == []

    async def test_static_default_kept(self):
        a = Item()
        await Item._apply_defaults(a)

        assert a.status == "draft"
        assert a.is_assigned("name") is False


class TestAddFields:
    def test_batch_adds_fields_with_one_rebuild(self, monkeypatch):
        class Thing(DotModel):
            __table__ = "t_cache_thing"

            id: int = Integer(primary_key=True)

        calls: list[int] = []
        original = Thing.rebuild_field_caches

        def counting():
            calls.append(1)
            original()

        monkeypatch.setattr(Thing, "rebuild_field_caches", counting)
        Thing.add_fields({"code": Char(), "qty": Integer(store=False)})

        assert calls == [1]
        assert list(Thing.get_fields()) == ["id", "code", "qty"]
        assert Thing.get_store_fields() == ["id", "code"]
        # билдер пересобран по новым полям
        assert "code" in Thing._builder.fields
        assert Thing._builder.get_store_fields() == ["id", "code"]


class TestStoreFields:
    def test_get_store_fields_matches_dict_and_is_a_copy(self):
        fields = Item.get_store_fields()

        assert fields == list(Item.get_store_fields_dict())
        assert "label" not in fields  # store=False

        fields.append("bogus")
        assert "bogus" not in Item.get_store_fields()


class TestProtocolSync:
    def test_protocol_declares_same_caches(self):
        model_caches = {
            name
            for name in DotModel.__annotations__
            if name.startswith("_cache_")
        }
        protocol_caches = {
            name
            for name in DotModelProtocol.__annotations__
            if name.startswith("_cache_")
        }

        assert protocol_caches == model_caches
