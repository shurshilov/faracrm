"""
Unit-тесты @constrains (decorators.constrains, DotModel._build_constrains_cache,
OrmPrimaryMixin._run_constrains).

Контракт: правило вызывается один раз на операцию со всеми записями
(одна у create/update, все строки у bulk; на update у каждой выставлен id),
ДО SQL и только если записываемые поля задевают его триггеры; движок в
базу не ходит — правило само батчит запросы и дочитывает нужные поля по
id записей в незаданные атрибуты payload, в SQL дочитанное не попадает;
исключение из правила = ни одного INSERT/UPDATE; метод, положенный на
класс после его определения (как делает @extend), виден после
rebuild_field_caches.

No database: сессия БД подменена на двойник, который запоминает SQL и
отдаёт «хранимые» строки на SELECT.
"""

from typing import Self

import pytest

from dotorm.decorators import constrains
from dotorm.fields import Char, Integer
from dotorm.model import DotModel
from dotorm.orm.mixins.primary import OrmPrimaryMixin

pytestmark = pytest.mark.unit


class FakeSession:
    """Двойник сессии БД: INSERT отдаёт id по числу строк, SELECT — все
    хранимые строки (через prepare, как asyncpg-записи), остальное копит."""

    def __init__(self, stored: list[dict]):
        self.calls: list[tuple[str, object]] = []
        self.stored = stored

    async def execute(
        self, stmt, values=None, *, prepare=None, cursor="fetchall"
    ):
        self.calls.append((stmt, values))
        if stmt.startswith("INSERT"):
            first = values[0] if values else None
            n = len(first) if isinstance(first, list) else 1
            return [{"id": i} for i in range(1, n + 1)]
        if stmt.startswith("SELECT"):
            rows = [dict(row) for row in self.stored]
            return prepare(rows) if prepare else rows
        return None

    def statements(self, prefix: str) -> list[str]:
        return [s for s, _ in self.calls if s.startswith(prefix)]


# (правило, id записи, login, name) — что и с чем вызывалось, по записям
RUNS: list[tuple[str, int | None, object, object]] = []
# (правило, сколько записей) — по вызовам
CALLS: list[tuple[str, int]] = []


async def read_names(model, records):
    """Как правило дочитывает поле вне payload на update: одним search по
    id всей пачки, значения клиента в приоритете."""
    ids = [r.id for r in records if r.id and not r.is_assigned("name")]
    if not ids:
        return
    stored = {
        row.id: row
        for row in await model.sudo().search(
            filter=[("id", "in", ids)], fields=["name"]
        )
    }
    for r in records:
        if r.id in stored and not r.is_assigned("name"):
            r.name = stored[r.id].name


class Account(DotModel):
    __table__ = "t_constrains_account"

    id: int = Integer(primary_key=True)
    login: str | None = Char()
    name: str | None = Char()
    kind: str = Char(default="user")

    @constrains("login")
    async def _check_login(self, records: list[Self]):
        CALLS.append(("login", len(records)))
        await read_names(self, records)
        for r in records:
            RUNS.append(("login", r.id, r.login, r.name))
            if r.login == "taken":
                raise ValueError("login taken")

    # Field-объект вместо строки — резолвится в имя при сборке кэша.
    # Ничего не дочитывает: видит только payload.
    @constrains(kind)
    async def _check_kind(self, records: list[Self]):
        CALLS.append(("kind", len(records)))
        for r in records:
            RUNS.append(("kind", r.id, r.kind, r.name))

    @constrains()
    async def _check_always(self, records: list[Self]):
        CALLS.append(("always", len(records)))
        await read_names(self, records)
        for r in records:
            RUNS.append(("always", r.id, None, r.name))


class Quiet(DotModel):
    """Проверка есть, но в базу не ходит (как выключенное правило)."""

    __table__ = "t_constrains_quiet"

    id: int = Integer(primary_key=True)
    code: str | None = Char()

    @constrains("code")
    async def _check_code(self, records: list[Self]):
        for r in records:
            RUNS.append(("code", r.id, r.code, None))


OrmPrimaryMixin._build_depends_tables([Account, Quiet])

STORED = [
    {"id": 1, "login": "l1", "name": "stored-1", "kind": "bot"},
    {"id": 2, "login": "l2", "name": "stored-2", "kind": "bot"},
    {"id": 7, "login": "l7", "name": "stored-7", "kind": "bot"},
]


@pytest.fixture
def session(monkeypatch):
    fake = FakeSession(stored=STORED)
    for model in (Account, Quiet):
        monkeypatch.setattr(
            model,
            "_get_db_session",
            classmethod(lambda cls, session=None, _f=fake: _f),
        )
    RUNS.clear()
    CALLS.clear()
    return fake


def rules(name: str) -> list[tuple[str, int | None, object, object]]:
    return [r for r in RUNS if r[0] == name]


def calls(name: str) -> list[int]:
    return [n for rule, n in CALLS if rule == name]


class TestCache:
    def test_collects_methods_with_resolved_trigger_fields(self):
        cache = dict(Account._cache_constrains)
        assert cache == {
            "_check_login": frozenset({"login"}),
            "_check_kind": frozenset({"kind"}),
            "_check_always": frozenset(),
        }

    def test_model_without_constrains_has_empty_cache(self):
        class Plain(DotModel):
            __table__ = "t_constrains_plain"
            id: int = Integer(primary_key=True)

        assert Plain._cache_constrains == ()

    def test_method_added_after_definition_visible_after_rebuild(self):
        # Так поступает @extend: setattr на готовый класс + rebuild_field_caches.
        @constrains("name")
        async def _check_ext(self, records: list[Self]):
            RUNS.append(("ext", None, None, None))

        setattr(Account, "_check_ext", _check_ext)
        try:
            assert "_check_ext" not in dict(Account._cache_constrains)
            Account.rebuild_field_caches()
            assert dict(Account._cache_constrains)["_check_ext"] == frozenset(
                {"name"}
            )
        finally:
            delattr(Account, "_check_ext")
            Account.rebuild_field_caches()
        assert "_check_ext" not in dict(Account._cache_constrains)


class TestCreate:
    async def test_runs_after_defaults_before_insert(self, session):
        record_id = await Account.create(Account(login="ok"))

        assert record_id == 1
        assert rules("login") == [("login", None, "ok", None)]
        # kind не задавали — его подставил default, и проверка его видит.
        assert rules("kind") == [("kind", None, "user", None)]
        assert rules("always") == [("always", None, None, None)]
        assert len(session.statements("INSERT")) == 1
        # На create дочитывать нечего: в базу не ходим.
        assert session.statements("SELECT") == []

    async def test_rejected_record_is_not_inserted(self, session):
        with pytest.raises(ValueError, match="login taken"):
            await Account.create(Account(login="taken"))

        assert session.statements("INSERT") == []

    async def test_untouched_trigger_skips_check(self, session):
        await Account.create(Account(name="no login here"))

        assert rules("login") == []
        assert rules("always") == [("always", None, None, "no login here")]


class TestUpdate:
    async def test_runs_only_for_written_fields_with_record_id(self, session):
        rec = Account(id=7)
        await rec.update(Account(name="renamed"), fields=["name"])

        assert rules("login") == []
        # name из payload — приоритет над хранимым, в базу не ходим.
        assert rules("always") == [("always", 7, None, "renamed")]
        assert session.statements("SELECT") == []
        assert len(session.statements("UPDATE")) == 1

    async def test_read_field_shared_by_checks_writes_only_fields(
        self, session
    ):
        rec = Account(id=7)
        payload = Account(login="fresh")
        await rec.update(payload, fields=["login"])

        # Первое правило дочитало name в payload, второе уже видит его —
        # SELECT один.
        assert rules("login") == [("login", 7, "fresh", "stored-7")]
        assert rules("always") == [("always", 7, None, "stored-7")]
        assert len(session.statements("SELECT")) == 1
        # Дочитанное в UPDATE не попало.
        stmt, values = next(
            c for c in session.calls if c[0].startswith("UPDATE")
        )
        assert '"name"' not in stmt
        assert "stored-7" not in (values or [])

    async def test_check_that_reads_nothing_costs_no_select(self, session):
        rec = Quiet(id=7)
        await rec.update(Quiet(code="x"), fields=["code"])

        assert rules("code") == [("code", 7, "x", None)]
        # Выключенное/нетребовательное правило — ни одного SELECT.
        assert session.statements("SELECT") == []

    async def test_rejected_update_is_not_written(self, session):
        rec = Account(id=7)
        with pytest.raises(ValueError, match="login taken"):
            await rec.update(Account(login="taken"))

        assert session.statements("UPDATE") == []


class TestBulk:
    async def test_create_bulk_one_call_with_all_rows(self, session):
        await Account.create_bulk([Account(login="a"), Account(login="b")])

        # Одно правило — один вызов со всей пачкой, не по строке.
        assert calls("login") == [2]
        assert rules("login") == [
            ("login", None, "a", None),
            ("login", None, "b", None),
        ]
        assert len(session.statements("INSERT")) == 1

    async def test_create_bulk_rejects_whole_batch_before_insert(
        self, session
    ):
        with pytest.raises(ValueError, match="login taken"):
            await Account.create_bulk(
                [Account(login="a"), Account(login="taken")]
            )

        assert session.statements("INSERT") == []

    async def test_create_bulk_trigger_from_any_row(self, session):
        await Account.create_bulk([Account(name="n"), Account(login="a")])

        # Триггер задет одной строкой — правило видит обе.
        assert calls("login") == [2]

    async def test_update_bulk_one_call_own_copy_per_id(self, session):
        payload = Account(login="z")
        await Account.update_bulk([1, 2], payload)

        # Один вызов, у каждой копии свой id и своё дочитанное name,
        # SELECT один на пачку.
        assert calls("login") == [2]
        assert rules("login") == [
            ("login", 1, "z", "stored-1"),
            ("login", 2, "z", "stored-2"),
        ]
        assert len(session.statements("SELECT")) == 1
        # Общий payload чист, UPDATE без дочитанного name.
        assert not payload.is_assigned("name")
        stmt, _ = next(c for c in session.calls if c[0].startswith("UPDATE"))
        assert '"name"' not in stmt
        assert len(session.statements("UPDATE")) == 1

    async def test_update_bulk_rejected_is_not_written(self, session):
        with pytest.raises(ValueError, match="login taken"):
            await Account.update_bulk([1, 2], Account(login="taken"))

        assert session.statements("UPDATE") == []
