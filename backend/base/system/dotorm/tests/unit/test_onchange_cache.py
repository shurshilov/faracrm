"""
Unit-тесты кэша @onchange (DotModel._build_onchange_cache).

Контракт: обработчики собираются один раз при создании класса и после
rebuild_field_caches (как делает @extend), а не обходом dir(cls) на каждый
запрос; порядок обработчиков одного поля — по алфавиту имён, как у dir():
расширения опираются на него при мёрже результатов в execute_onchange.
get_onchange_fields объединяет поля @onchange с триггерами @depends.

No database.
"""

import pytest

from dotorm.decorators import depends, onchange
from dotorm.fields import Char, Integer
from dotorm.model import DotModel

pytestmark = pytest.mark.unit


class Connector(DotModel):
    __table__ = "t_onchange_connector"

    id: int = Integer(primary_key=True)
    type: str | None = Char()
    url: str | None = Char()
    rate: int | None = Integer()
    total: int = Integer(default=0, compute="_compute_total")

    @onchange("type")
    async def onchange_type(self) -> dict:
        return {"url": "base"}

    # Имя сортируется после onchange_type — при мёрже перекрывает базовый.
    @onchange("type")
    async def onchange_type_ext(self) -> dict:
        return {"url": "ext"}

    @onchange("url")
    async def onchange_url(self) -> dict:
        return {}

    @depends(triggers=[rate])
    async def _compute_total(self) -> None:
        self.total = (self.rate or 0) * 2


# Кэш собирается по __dict__ вдоль MRO: обработчики базового класса видны
# в наследнике, переопределённое имя берётся из наследника и не дублируется.
class OnchangeMixin(DotModel):
    @onchange("type")
    async def onchange_type_base(self) -> dict:
        return {"url": "mixin"}


class MixedConnector(OnchangeMixin):
    __table__ = "t_onchange_mixed"

    id: int = Integer(primary_key=True)
    type: str | None = Char()
    url: str | None = Char()

    @onchange("type")
    async def onchange_type_own(self) -> dict:
        return {"url": "own"}


class OverridingConnector(OnchangeMixin):
    __table__ = "t_onchange_override"

    id: int = Integer(primary_key=True)
    type: str | None = Char()
    url: str | None = Char()

    @onchange("type", "url")
    async def onchange_type_base(self) -> dict:
        return {}


class TestOnchangeCache:
    def test_cache_maps_field_to_handlers_in_dir_order(self):
        assert Connector._cache_onchange == {
            "type": ["onchange_type", "onchange_type_ext"],
            "url": ["onchange_url"],
        }
        assert Connector._get_onchange_handlers("type") == [
            "onchange_type",
            "onchange_type_ext",
        ]
        assert Connector._get_onchange_handlers("missing") == []

    def test_onchange_fields_include_depends_triggers(self):
        assert set(Connector.get_onchange_fields()) == {"type", "url", "rate"}

    def test_handler_added_after_definition_visible_after_rebuild(self):
        # Так поступает @extend: setattr на готовый класс + rebuild_field_caches.
        @onchange("rate")
        async def onchange_rate(self) -> dict:
            return {}

        setattr(Connector, "onchange_rate", onchange_rate)
        try:
            assert "rate" not in Connector._cache_onchange
            Connector.rebuild_field_caches()
            assert Connector._cache_onchange["rate"] == ["onchange_rate"]
        finally:
            delattr(Connector, "onchange_rate")
            Connector.rebuild_field_caches()
        assert "rate" not in Connector._cache_onchange

    async def test_execute_onchange_merges_handlers_in_order(self):
        rec = Connector(type="x")
        result = await rec.execute_onchange("type")
        # Последний по алфавиту обработчик перекрывает базовый.
        assert result["url"] == "ext"

    def test_handlers_of_base_class_collected_in_name_order(self):
        assert MixedConnector._cache_onchange == {
            "type": ["onchange_type_base", "onchange_type_own"],
        }

    def test_override_in_subclass_replaces_base_handler(self):
        assert OverridingConnector._cache_onchange == {
            "type": ["onchange_type_base"],
            "url": ["onchange_type_base"],
        }

    async def test_execute_onchange_runs_base_then_own(self):
        rec = MixedConnector(type="x")
        result = await rec.execute_onchange("type")
        assert result["url"] == "own"
