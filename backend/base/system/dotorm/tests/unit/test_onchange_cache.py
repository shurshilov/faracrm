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
