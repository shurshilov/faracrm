"""
Интеграционные тесты связей при создании и в bulk-операциях.

Контракт dotorm (2026-09-22):
- create() пишет связи из payload сам (update после INSERT): команды
  selected/created и списки записей (с id — selected, без id — created);
  x2m-дефолт с default_orm (User.lang_ids) ложится на payload и тоже
  пишется; явно заданное поле, даже пустое, важнее дефолта;
- role_ids: default_orm=False — дефолт видит только форма
  (get_default_values), код не привязывает;
- create_bulk: связи первой строки одним update_bulk на всю пачку;
- update_bulk: одни команды на все ids, запрос на поле — M2M
  selected/unselected только у владельцев, новые дети O2M каждому владельцу,
  словарь формы не мутируется;
- create-роут автокруда — один create, дети не дублируются.

Run: pytest tests/integration/test_relations_on_create.py -v -m integration
"""

from datetime import datetime, timezone
from typing import Any

import pytest

from tests.conftest import auto

from backend.base.crm.activity.models.activity import Activity
from backend.base.crm.activity.models.activity_type import ActivityType
from backend.base.crm.languages.models.language import Language
from backend.base.crm.partners.models.partners import Partner
from backend.base.crm.products.models.product import Product
from backend.base.crm.sales.models.sale import Sale
from backend.base.crm.sales.models.sale_line import SaleLine
from backend.base.crm.sales.models.sale_stage import SaleStage
from backend.base.crm.security.models.roles import Role
from backend.base.crm.users.models.users import User

pytestmark = [pytest.mark.integration, pytest.mark.api]


# ====================
# Helpers
# ====================
# Поля-связи объявлены записями (list["Role"], "Partner | None"), поэтому
# в payload — инстансы; команды формы (словари selected/created) — это
# контракт API, а не тип поля, отсюда Any.


def selected(*ids: int) -> Any:
    return {"selected": list(ids)}


def unselected(*ids: int) -> Any:
    return {"unselected": list(ids)}


def created(*rows: dict) -> Any:
    return {"created": list(rows)}


def refs(*items: Any) -> Any:
    """Список ссылок на записи: инстансы вперемешку с голыми id."""
    return list(items)


async def _language(code: str, name: str) -> Language:
    """Язык по коду: «en» сидится фикстурой, второй раз не создаём —
    дефолт lang_ids ищет по коду и получил бы дубль."""
    existing = await Language.search_one(
        filter=[("code", "=", code)], fields=["id"]
    )
    if existing:
        return existing
    return Language(
        id=await Language.create(Language(code=code, name=name, active=True))
    )


async def _languages() -> tuple[Language, Language]:
    return await _language("en", "English"), await _language("ru", "Русский")


async def _role(code: str, name: str = "Role") -> Role:
    return Role(id=await Role.create(Role(code=code, name=name)))


async def _user(login: str, **kwargs: Any) -> int:
    return await User.create(
        User(
            name=f"User {login}",
            login=login,
            password_hash="h",
            password_salt="s",
            **kwargs,
        )
    )


async def _user_links(user_id: int) -> tuple[set[str], set[str]]:
    """(коды ролей, коды языков) пользователя."""
    user = await User.get(
        user_id,
        fields=["id", "role_ids", "lang_ids"],
        fields_nested={
            "role_ids": {"fields": ["id", "code"]},
            "lang_ids": {"fields": ["id", "code"]},
        },
    )
    assert user is not None
    return (
        {r.code for r in user.role_ids or []},
        {l.code for l in user.lang_ids or []},
    )


async def _user_name(user_id: int) -> str:
    user = await User.get(user_id, fields=["id", "name"])
    assert user is not None
    return user.name


async def _sale_setup() -> tuple[SaleStage, Partner, Product]:
    stage = SaleStage(
        id=await SaleStage.create(SaleStage(name="Draft", sequence=1))
    )
    partner = Partner(id=await Partner.create(Partner(name="Customer")))
    product = Product(
        id=await Product.create(Product(name="Widget", list_price=10.0))
    )
    return stage, partner, product


async def _sale(
    name: str, stage: SaleStage, partner: Partner, **kwargs: Any
) -> int:
    return await Sale.create(
        Sale(name=name, partner_id=partner, stage_id=stage, **kwargs)
    )


def _line(product: Product, qty: float) -> SaleLine:
    """Новая позиция без родителя — FK проставит ORM."""
    return SaleLine(product_id=product, product_uom_qty=qty, price_unit=10.0)


def _line_row(product: Product, qty: float) -> dict:
    """Строка позиции в форме created (как шлёт форма: FK = VirtualId)."""
    return {
        "sale_id": "VirtualId",
        "product_id": product.id,
        "product_uom_qty": qty,
        "price_unit": 10.0,
    }


async def _lines(sale_id: int) -> list[SaleLine]:
    return await SaleLine.search(
        fields=["id", "sale_id", "product_uom_qty"],
        filter=[("sale_id", "=", sale_id)],
        sort="id",
        order="ASC",
    )


# ====================
# create() со связями (ORM)
# ====================


class TestCreateWithRelationsORM:
    async def test_default_languages_linked_on_create(self, db_pool):
        """Дефолт lang_ids (en + ru) пишется при создании кодом — та самая
        причина пустых языков у сидеров."""
        await _languages()

        user_id = await _user("lang_default")

        _, langs = await _user_links(user_id)
        assert langs == {"en", "ru"}

    async def test_explicit_empty_languages_win_over_default(self, db_pool):
        await _languages()

        user_id = await _user("lang_empty", lang_ids=[])

        _, langs = await _user_links(user_id)
        assert langs == set()

    async def test_explicit_language_command_wins_over_default(self, db_pool):
        _, ru = await _languages()

        user_id = await _user("lang_cmd", lang_ids=selected(ru.id))

        _, langs = await _user_links(user_id)
        assert langs == {"ru"}

    async def test_base_user_role_default_is_form_only(self, db_pool):
        """role_ids: default_orm=False — код не привязывает, форма видит."""
        await _role("base_user", "Internal User")

        user_id = await _user("role_form_only")

        roles, _ = await _user_links(user_id)
        assert roles == set()
        # Строки дефолта x2m — json_list записи ({id, name}); вложенные
        # fields описывают колонки формы, а не состав строк.
        defaults = await User.get_default_values(
            {"role_ids": {"fields": ["id", "name"]}}
        )
        assert [r["name"] for r in defaults["role_ids"]["data"]] == [
            "Internal User"
        ]

    async def test_roles_selected_in_create(self, db_pool):
        r1 = await _role("create_r1")
        r2 = await _role("create_r2")

        user_id = await _user("roles_cmd", role_ids=selected(r1.id, r2.id))

        roles, _ = await _user_links(user_id)
        assert roles == {"create_r1", "create_r2"}

    async def test_roles_as_record_list_in_create(self, db_pool):
        """Список записей и голых id равносилен команде selected."""
        r1 = await _role("list_r1")
        r2 = await _role("list_r2")

        user_id = await _user("roles_list", role_ids=refs(r1, r2.id))

        roles, _ = await _user_links(user_id)
        assert roles == {"list_r1", "list_r2"}

    async def test_new_role_record_is_created_and_linked(self, db_pool):
        """Запись без id в списке — created: создаётся и привязывается."""
        user_id = await _user(
            "roles_new", role_ids=[Role(code="fresh_role", name="Fresh")]
        )

        roles, _ = await _user_links(user_id)
        assert roles == {"fresh_role"}
        fresh = await Role.search(
            fields=["id"], filter=[("code", "=", "fresh_role")]
        )
        assert len(fresh) == 1

    async def test_sale_lines_created_with_virtual_id(self, db_pool):
        stage, partner, product = await _sale_setup()

        rows = [_line_row(product, 1), _line_row(product, 2)]
        sale_id = await _sale(
            "SO-CREATE-1", stage, partner, order_line_ids=created(*rows)
        )

        lines = await _lines(sale_id)
        assert [line.product_uom_qty for line in lines] == [1.0, 2.0]
        assert all(line.sale_id.id == sale_id for line in lines)

    async def test_sale_lines_as_new_records_get_parent(self, db_pool):
        """Ребёнок из кода родителя не знает — FK проставляет ORM."""
        stage, partner, product = await _sale_setup()

        sale_id = await _sale(
            "SO-CREATE-2", stage, partner, order_line_ids=[_line(product, 3)]
        )

        lines = await _lines(sale_id)
        assert len(lines) == 1
        assert lines[0].sale_id.id == sale_id

    async def test_polymorphic_children_get_owner(self, db_pool):
        """Полиморфный ребёнок из кода получает res_id и res_model."""
        activity_type = ActivityType(
            id=await ActivityType.create(ActivityType(name="Call"))
        )
        partner = Partner(name="With activity")
        # activity_ids навешивается на модель при старте — IDE его не видит
        setattr(
            partner,
            "activity_ids",
            [
                Activity(
                    summary="call back",
                    activity_type_id=activity_type,
                    date_deadline=datetime.now(timezone.utc),
                )
            ],
        )

        partner_id = await Partner.create(partner)

        activities = await Activity.search(
            fields=["id", "res_model", "res_id", "summary"],
            filter=[("res_id", "=", partner_id)],
        )
        assert [a.summary for a in activities] == ["call back"]
        assert activities[0].res_model == Partner.__table__


# ====================
# update() со списками записей
# ====================


class TestUpdateWithLists:
    async def test_many2many_record_list(self, db_pool):
        role = await _role("upd_list")
        user_id = await _user("upd_list")

        user = await User.get(user_id)
        assert user is not None
        await user.update(User(role_ids=[role]))

        roles, _ = await _user_links(user_id)
        assert roles == {"upd_list"}

    async def test_one2many_new_record_list(self, db_pool):
        stage, partner, product = await _sale_setup()
        sale_id = await _sale("SO-UPD", stage, partner)

        sale = await Sale.get(sale_id)
        assert sale is not None
        await sale.update(Sale(order_line_ids=[_line(product, 4)]))

        lines = await _lines(sale_id)
        assert [line.product_uom_qty for line in lines] == [4.0]
        assert lines[0].sale_id.id == sale_id

    async def test_form_dict_is_not_mutated(self, db_pool):
        stage, partner, product = await _sale_setup()
        sale_id = await _sale("SO-DICT", stage, partner)
        row = _line_row(product, 1)

        sale = await Sale.get(sale_id)
        assert sale is not None
        await sale.update(Sale(order_line_ids=created(row)))

        assert row["sale_id"] == "VirtualId"
        assert len(await _lines(sale_id)) == 1


# ====================
# create_bulk
# ====================


class TestCreateBulk:
    async def test_users_get_default_languages(self, db_pool):
        await _languages()

        rows = await User.create_bulk(
            [
                User(name=f"Bulk {i}", login=f"bulk_{i}", password_hash="h")
                for i in range(3)
            ]
        )

        assert len(rows) == 3
        for row in rows:
            _, langs = await _user_links(row["id"])
            assert langs == {"en", "ru"}

    async def test_first_row_relations_apply_to_whole_batch(self, db_pool):
        """Связи в bulk — одни на пачку (дефолты); берутся с первой строки."""
        role = await _role("bulk_role")

        rows = await User.create_bulk(
            [
                User(
                    name="Bulk A",
                    login="bulk_a",
                    password_hash="h",
                    role_ids=selected(role.id),
                ),
                User(name="Bulk B", login="bulk_b", password_hash="h"),
            ]
        )

        for row in rows:
            roles, _ = await _user_links(row["id"])
            assert roles == {"bulk_role"}

    async def test_children_for_each_owner(self, db_pool):
        stage, partner, product = await _sale_setup()

        rows = await Sale.create_bulk(
            [
                Sale(
                    name="SO-BULK-1",
                    partner_id=partner,
                    stage_id=stage,
                    order_line_ids=[_line(product, 5)],
                ),
                Sale(name="SO-BULK-2", partner_id=partner, stage_id=stage),
            ]
        )

        for row in rows:
            lines = await _lines(row["id"])
            assert [line.product_uom_qty for line in lines] == [5.0]
            assert lines[0].sale_id.id == row["id"]

    async def test_without_relations_only_insert(self, db_pool):
        rows = await SaleStage.create_bulk(
            [
                SaleStage(name="S1", sequence=1),
                SaleStage(name="S2", sequence=2),
            ]
        )

        stages = await SaleStage.search(
            fields=["id"], filter=[("name", "in", ["S1", "S2"])]
        )
        assert sorted(s.id for s in stages) == sorted(r["id"] for r in rows)


# ====================
# update_bulk
# ====================


class TestUpdateBulk:
    async def _users(self, *logins: str) -> list[int]:
        return [await _user(login) for login in logins]

    async def _sales(self, count: int) -> tuple[list[int], Product]:
        stage, partner, product = await _sale_setup()
        sales = [await _sale(f"SO-{i}", stage, partner) for i in range(count)]
        return sales, product

    async def test_store_fields_only(self, db_pool):
        role = await _role("keep")
        a, b = await self._users("st_a", "st_b")
        await User.update_bulk([a], User(role_ids=selected(role.id)))

        await User.update_bulk([a, b], User(name="Renamed"))

        assert [await _user_name(i) for i in (a, b)] == ["Renamed"] * 2
        roles, _ = await _user_links(a)
        assert roles == {"keep"}  # связи не тронуты

    async def test_select_role_only_for_ids(self, db_pool):
        role = await _role("sel_all")
        a, b, c = await self._users("sel_a", "sel_b", "sel_c")

        await User.update_bulk([a, b], User(role_ids=selected(role.id)))

        expected = {a: {"sel_all"}, b: {"sel_all"}, c: set()}
        for user_id, codes in expected.items():
            roles, _ = await _user_links(user_id)
            assert roles == codes

    async def test_unselect_role_only_for_owners(self, db_pool):
        """DELETE по владельцам IN (...): у чужой записи связь остаётся."""
        role = await _role("unsel")
        a, b, c = await self._users("unsel_a", "unsel_b", "unsel_c")
        await User.update_bulk([a, b, c], User(role_ids=selected(role.id)))

        await User.update_bulk([a, b], User(role_ids=unselected(role.id)))

        expected = {a: set(), b: set(), c: {"unsel"}}
        for user_id, codes in expected.items():
            roles, _ = await _user_links(user_id)
            assert roles == codes

    async def test_relations_only_payload(self, db_pool):
        """Только связи — без SQL UPDATE, поля записей не меняются."""
        role = await _role("only_rel")
        a, b = await self._users("rel_a", "rel_b")

        await User.update_bulk([a, b], User(role_ids=selected(role.id)))

        assert await _user_name(a) == "User rel_a"
        roles, _ = await _user_links(b)
        assert roles == {"only_rel"}

    async def test_store_and_relations_together(self, db_pool):
        role = await _role("both")
        a, b = await self._users("both_a", "both_b")

        await User.update_bulk(
            [a, b], User(name="Both", role_ids=selected(role.id))
        )

        for user_id in (a, b):
            assert await _user_name(user_id) == "Both"
            roles, _ = await _user_links(user_id)
            assert roles == {"both"}

    async def test_one2many_created_for_each_owner(self, db_pool):
        sales, product = await self._sales(2)
        row = _line_row(product, 7)

        await Sale.update_bulk(sales, Sale(order_line_ids=created(row)))

        for sale_id in sales:
            lines = await _lines(sale_id)
            assert [line.product_uom_qty for line in lines] == [7.0]
            assert lines[0].sale_id.id == sale_id
        assert row["sale_id"] == "VirtualId"  # словарь формы не мутирован

    async def test_one2many_new_record_list_for_each_owner(self, db_pool):
        sales, product = await self._sales(2)

        await Sale.update_bulk(sales, Sale(order_line_ids=[_line(product, 8)]))

        for sale_id in sales:
            lines = await _lines(sale_id)
            assert [line.product_uom_qty for line in lines] == [8.0]

    async def test_many2many_created_role_linked_to_all(self, db_pool):
        """created у M2M: одна новая запись, привязана ко всем ids."""
        a, b = await self._users("m2m_new_a", "m2m_new_b")

        await User.update_bulk(
            [a, b],
            User(role_ids=created({"code": "bulk_new", "name": "Bulk"})),
        )

        roles = await Role.search(
            fields=["id"], filter=[("code", "=", "bulk_new")]
        )
        assert len(roles) == 1
        for user_id in (a, b):
            codes, _ = await _user_links(user_id)
            assert codes == {"bulk_new"}

    async def test_empty_ids_is_noop(self, db_pool):
        role = await _role("noop")
        (a,) = await self._users("noop_a")

        result = await User.update_bulk(
            [], User(name="X", role_ids=selected(role.id))
        )

        assert result is None
        assert await _user_name(a) == "User noop_a"
        roles, _ = await _user_links(a)
        assert roles == set()


# ====================
# API: create-роут = один create
# ====================


class TestCreateAPI:
    async def test_create_user_with_roles_and_default_languages(
        self, authenticated_client
    ):
        client, _, _ = authenticated_client
        en, _ = await _languages()
        role = await _role("api_role")

        response = await client.post(
            auto("/users"),
            json={
                "name": "API User",
                "login": "api_user",
                "lang_id": en.id,
                "role_ids": selected(role.id),
            },
        )

        assert response.status_code == 200, response.text
        roles, langs = await _user_links(response.json()["id"])
        assert roles == {"api_role"}
        assert langs == {"en", "ru"}

    async def test_create_sale_lines_once(self, authenticated_client):
        """Роут больше не зовёт update после create — дети ровно один раз."""
        client, _, _ = authenticated_client
        stage, partner, product = await _sale_setup()

        response = await client.post(
            auto("/sales"),
            json={
                "name": "SO-API",
                "partner_id": partner.id,
                "stage_id": stage.id,
                "order_line_ids": created(
                    _line_row(product, 1), _line_row(product, 2)
                ),
            },
        )

        assert response.status_code == 200, response.text
        lines = await _lines(response.json()["id"])
        assert [line.product_uom_qty for line in lines] == [1.0, 2.0]

    async def test_default_values_show_form_only_role_default(
        self, authenticated_client
    ):
        client, _, _ = authenticated_client
        await _languages()
        await _role("base_user", "Internal User")

        response = await client.post(
            auto("/users/default_values"),
            json={
                "fields": [
                    "name",
                    {"role_ids": ["id", "name"]},
                    {"lang_ids": ["id", "name"]},
                ]
            },
        )

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        # Строки дефолта — json_list записи ({id, name}), см. тест ORM выше.
        assert [r["name"] for r in data["role_ids"]["data"]] == [
            "Internal User"
        ]
        assert {l["name"] for l in data["lang_ids"]["data"]} == {
            "English",
            "Русский",
        }

    async def test_update_bulk_roles(self, authenticated_client):
        client, _, _ = authenticated_client
        role = await _role("api_bulk")
        a = await _user("api_bulk_a")
        b = await _user("api_bulk_b")

        response = await client.put(
            auto("/users/bulk"),
            json={"ids": [a, b], "values": {"role_ids": selected(role.id)}},
        )

        assert response.status_code == 200, response.text
        for user_id in (a, b):
            roles, _ = await _user_links(user_id)
            assert roles == {"api_bulk"}
