"""
Unit-тесты очереди @depends (orm/mixins/primary.py).

Контракт: CRUD только помечает (модель, метод) → {id}, owner сливает
очередь один раз в конце операции:
- ключ считается группой — один SELECT недостающих записей, один SELECT
  на relation-голову (id IN / fk IN) и один UPDATE ... FROM unnest;
- повторные пометки ключа схлопываются (несколько команд O2M в одном
  update, цепочка методов одной модели) — лишних пересчётов нет;
- дети считаются раньше родителей, в каком бы порядке их ни пометили.

No database, no network: сессия БД подменена на двойник, который запоминает
SQL, search — на фейки.
"""

import pytest

from dotorm.decorators import depends
from dotorm.fields import Integer, Many2one, One2many
from dotorm.model import DotModel
from dotorm.orm.mixins.primary import OrmPrimaryMixin

pytestmark = pytest.mark.unit


class FakeSession:
    """Двойник сессии БД: INSERT отдаёт id по числу строк, остальное копит."""

    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    async def execute(
        self, stmt, values=None, *, prepare=None, cursor="fetchall"
    ):
        self.calls.append((stmt, values))
        if stmt.startswith("INSERT"):
            # bulk — unnest-массивы (values[0] список), single — скаляры
            first = values[0] if values else None
            n = len(first) if isinstance(first, list) else 1
            return [{"id": i} for i in range(1, n + 1)]
        return None

    def updates(self) -> list[tuple[str, object]]:
        return [c for c in self.calls if c[0].startswith("UPDATE")]

    def updated_tables(self) -> list[str]:
        return [stmt.split()[1] for stmt, _ in self.updates()]


# ── локальный compute с M2O-prefetch (как Lead.progress по стадии) ──


class Stage(DotModel):
    __table__ = "t_bulk_stage"

    id: int = Integer(primary_key=True)
    sequence: int | None = Integer()


class Lead(DotModel):
    __table__ = "t_bulk_lead"

    id: int = Integer(primary_key=True)
    stage_id: "Stage | None" = Many2one(relation_table=Stage)
    progress: int = Integer(default=0, compute="_compute_progress")

    @depends(triggers=[stage_id], prefetch=[(stage_id, "sequence")])
    async def _compute_progress(self) -> None:
        self.progress = (self.stage_id.sequence or 0) * 10


# ── родитель с O2M-агрегацией (как Sale.amount_* по строкам) ──


class Order(DotModel):
    __table__ = "t_bulk_order"

    id: int = Integer(primary_key=True)
    total: int = Integer(default=0, compute="_compute_total")
    line_ids: list["Line"] = One2many(
        relation_table=lambda: Line, relation_table_field="order_id"
    )

    @depends(triggers_with_prefetch=[(line_ids, "amount")])
    async def _compute_total(self) -> None:
        lines = self.line_ids if isinstance(self.line_ids, list) else []
        self.total = sum(line.amount or 0 for line in lines)


class Line(DotModel):
    __table__ = "t_bulk_line"

    id: int = Integer(primary_key=True)
    order_id: "Order | None" = Many2one(relation_table=lambda: Order)
    amount: int | None = Integer()


# ── ребёнок со своим compute + родитель по нему (как SaleLine → Sale) ──


class Cart(DotModel):
    __table__ = "t_bulk_cart"

    id: int = Integer(primary_key=True)
    total: int = Integer(default=0, compute="_compute_total")
    item_ids: list["Item"] = One2many(
        relation_table=lambda: Item, relation_table_field="cart_id"
    )

    @depends(triggers_with_prefetch=[(item_ids, "amount")])
    async def _compute_total(self) -> None:
        items = self.item_ids if isinstance(self.item_ids, list) else []
        self.total = sum(item.amount or 0 for item in items)


class Item(DotModel):
    __table__ = "t_bulk_item"

    id: int = Integer(primary_key=True)
    cart_id: "Cart | None" = Many2one(relation_table=lambda: Cart)
    qty: int | None = Integer()
    price: int | None = Integer()
    amount: int = Integer(default=0, compute="_compute_amount")

    @depends(triggers=[qty, price])
    async def _compute_amount(self) -> None:
        self.amount = (self.qty or 0) * (self.price or 0)


# ── цепочка двух методов одной модели: a → b → c, при этом c зависит и от a ──

CHAIN_RUNS: list[str] = []


class Chain(DotModel):
    __table__ = "t_bulk_chain"

    id: int = Integer(primary_key=True)
    a: int | None = Integer()
    b: int = Integer(default=0, compute="_compute_b")
    c: int = Integer(default=0, compute="_compute_c")

    @depends(triggers=[a])
    async def _compute_b(self) -> None:
        CHAIN_RUNS.append("_compute_b")
        self.b = (self.a or 0) * 2

    @depends(triggers=[a, b])
    async def _compute_c(self) -> None:
        CHAIN_RUNS.append("_compute_c")
        self.c = (self.a or 0) + (self.b or 0)


# ── @depends() без триггеров: значение зависит от всей таблицы (как процент стадии) ──


class Ref(DotModel):
    __table__ = "t_bulk_ref"

    id: int = Integer(primary_key=True)
    value: int | None = Integer()
    share: int = Integer(default=0, compute="_compute_share")

    @depends()
    async def _compute_share(self) -> None:
        self.share = (self.value or 0) * 10


MODELS = [Stage, Lead, Order, Line, Cart, Item, Chain, Ref]
OrmPrimaryMixin._build_depends_tables(MODELS)


@pytest.fixture
def session(monkeypatch):
    fake = FakeSession()
    for model in MODELS:
        monkeypatch.setattr(
            model,
            "_get_db_session",
            classmethod(lambda cls, session=None, _f=fake: _f),
        )
    return fake


class TestLocalComputeBulk:
    async def test_one_prefetch_and_one_update_for_all_rows(
        self, monkeypatch, session
    ):
        searches = []

        async def fake_stage_search(**kwargs):
            searches.append(kwargs)
            return [Stage(id=1, sequence=1), Stage(id=2, sequence=3)]

        monkeypatch.setattr(Stage, "search", fake_stage_search)

        await Lead.create_bulk(
            [Lead(stage_id=1), Lead(stage_id=2), Lead(stage_id=1)]
        )

        # Стадии догружены одним SELECT по всем FK.
        assert len(searches) == 1
        assert searches[0]["filter"] == [("id", "in", [1, 2])]
        assert set(searches[0]["fields"]) == {"id", "sequence"}

        # progress записан одним UPDATE ... FROM unnest, а не тремя.
        stmt, values = session.updates()[0]
        assert len(session.updates()) == 1
        assert stmt == (
            'UPDATE t_bulk_lead SET "progress" = v."progress" '
            "FROM unnest($1::int4[], $2::int4[]) "
            'AS v("id", "progress") WHERE t_bulk_lead.id = v.id'
        )
        assert values == [[1, 2, 3], [10, 30, 10]]

    async def test_update_bulk_skips_reread_without_trigger(
        self, monkeypatch, session
    ):
        async def unexpected(**kwargs):
            raise AssertionError("search must not be called")

        monkeypatch.setattr(Lead, "search", unexpected)

        await Lead.update_bulk([1, 2], Lead(progress=5))

        # Только сам UPDATE: progress не триггер, перечитывать строки незачем.
        assert len(session.updates()) == 1


class TestParentComputeBulk:
    async def test_parents_and_children_loaded_in_one_query_each(
        self, monkeypatch, session
    ):
        order_searches = []
        line_searches = []

        async def fake_order_search(**kwargs):
            order_searches.append(kwargs)
            return [Order(id=1), Order(id=2)]

        async def fake_line_search(**kwargs):
            line_searches.append(kwargs)
            # raw-строки как из БД: FK — голый int
            return [
                {"id": 1, "amount": 5, "order_id": 1},
                {"id": 2, "amount": 7, "order_id": 1},
                {"id": 3, "amount": 11, "order_id": 2},
            ]

        monkeypatch.setattr(Order, "search", fake_order_search)
        monkeypatch.setattr(Line, "search", fake_line_search)

        await Line.create_bulk(
            [
                Line(order_id=1, amount=5),
                Line(order_id=1, amount=7),
                Line(order_id=2, amount=11),
            ]
        )

        assert len(order_searches) == 1
        assert order_searches[0]["filter"] == [("id", "in", [1, 2])]

        assert len(line_searches) == 1
        assert line_searches[0]["filter"] == [("order_id", "in", [1, 2])]
        assert line_searches[0]["raw"] is True

        stmt, values = session.updates()[0]
        assert len(session.updates()) == 1
        assert stmt.startswith('UPDATE t_bulk_order SET "total" = v."total"')
        assert values == [[1, 2], [12, 11]]

    async def test_delete_and_create_in_one_scope_recompute_parent_once(
        self, monkeypatch, session
    ):
        order_searches = []

        async def fake_order_search(**kwargs):
            order_searches.append(kwargs)
            return [Order(id=1)]

        async def fake_line_search(**kwargs):
            if kwargs.get("raw"):
                # prefetch детей родителя
                return [{"id": 1, "amount": 5, "order_id": 1}]
            # pre-fetch строк перед delete_bulk (нужны FK)
            return [Line(id=9, order_id=1, amount=3)]

        monkeypatch.setattr(Order, "search", fake_order_search)
        monkeypatch.setattr(Line, "search", fake_line_search)

        # Как Sale.update с командами O2M: delete_bulk и create_bulk строк
        # копят пометки в одну очередь, сливает её owner.
        jobs: dict = {}
        await Line.delete_bulk([9], depends_jobs=jobs)
        await Line.create_bulk([Line(order_id=1, amount=5)], depends_jobs=jobs)
        assert order_searches == []  # до слива ничего не считалось

        await Line._depends_flush(jobs, True, session)

        # Родитель перечитан и пересчитан один раз, а не по разу на команду.
        assert len(order_searches) == 1
        assert session.updated_tables() == ["t_bulk_order"]
        assert 5 in session.updates()[0][1]


class TestQueueOrder:
    async def test_children_run_before_parent_regardless_of_mark_order(
        self, monkeypatch, session
    ):
        cart_searches = []

        async def fake_cart_search(**kwargs):
            cart_searches.append(kwargs)
            return [Cart(id=1)]

        async def fake_item_search(**kwargs):
            # raw-строки для prefetch родителя: amount уже пересчитан
            return [
                {"id": 1, "amount": 6, "cart_id": 1},
                {"id": 2, "amount": 20, "cart_id": 1},
            ]

        monkeypatch.setattr(Cart, "search", fake_cart_search)
        monkeypatch.setattr(Item, "search", fake_item_search)

        items = [
            Item(id=1, cart_id=1, qty=2, price=3),
            Item(id=2, cart_id=1, qty=4, price=5),
        ]
        jobs: dict = {}
        Item._depends_mark_parents(items, ["cart_id"], jobs)  # родитель первым
        Item._depends_mark(items, ["qty"], jobs)  # строки — после него
        assert list(jobs) == [
            (Cart, "_compute_total"),
            (Item, "_compute_amount"),
        ]

        await Item._depends_run(jobs, session)

        # Строки посчитаны раньше корзины, и каждая таблица — одним UPDATE:
        # корзина не пересчитывалась второй раз после каскада от строк.
        assert session.updated_tables() == ["t_bulk_item", "t_bulk_cart"]
        assert session.updates()[0][1] == [[1, 2], [6, 20]]
        assert 26 in session.updates()[1][1]
        assert len(cart_searches) == 1

    async def test_chain_runs_downstream_method_once(self, session):
        CHAIN_RUNS.clear()
        rec = Chain(id=1, a=1, b=0, c=0)

        await rec.update(Chain(a=2))

        # a триггерит и b, и c; b пишет поле, которое снова триггерит c —
        # c ставится в очередь один раз и считается уже после b.
        assert CHAIN_RUNS == ["_compute_b", "_compute_c"]
        assert (rec.b, rec.c) == (4, 6)
        assert session.updated_tables() == ["t_bulk_chain"] * 3


class TestAlwaysRecompute:
    """@depends() без триггеров: после любой операции над моделью
    пересчитываются все её записи одним SELECT и одним UPDATE."""

    async def test_any_write_recomputes_all_rows(self, monkeypatch, session):
        searches = []

        async def fake_ref_search(**kwargs):
            searches.append(kwargs)
            return [Ref(id=1, value=1), Ref(id=2, value=2), Ref(id=3, value=3)]

        monkeypatch.setattr(Ref, "search", fake_ref_search)

        await Ref.create(Ref(value=1))  # value — не триггер, но операция
        await Ref.delete_bulk([2])  # у удаления нет своих computes, но тоже

        # На каждую операцию — одна загрузка ВСЕХ строк (без filter)
        # и один UPDATE ... FROM unnest на всех.
        assert len(searches) == 2
        assert all("filter" not in s for s in searches)
        assert session.updated_tables() == ["t_bulk_ref", "t_bulk_ref"]
        assert session.updates()[0][1] == [[1, 2, 3], [10, 20, 30]]

    async def test_recompute_all_backfills_table(self, monkeypatch, session):
        async def fake_ref_search(**kwargs):
            return [Ref(id=1, value=4), Ref(id=2, value=5)]

        monkeypatch.setattr(Ref, "search", fake_ref_search)

        await Ref.recompute_all()

        assert session.updated_tables() == ["t_bulk_ref"]
        assert session.updates()[0][1] == [[1, 2], [40, 50]]
