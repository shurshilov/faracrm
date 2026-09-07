"""
Регрессионные тесты на инъекции и утечки в auto-CRUD (dotorm_crud_auto).

Решение, которое фиксируют тесты:
  * имя поля в filter ОБЯЗАНО быть не-private полем модели — одна проверка
    в FilterParser (через него проходят ВСЕ фильтры: API, rules-домены,
    домены папок чата); ValueError → роут search отвечает 400;
  * из API-схем private режется в одном месте — DotModel.get_public_fields().

Запуск:
    pytest tests/integration/test_crud_injection.py -v -m integration

В этом каталоге активен базовый (пермиссивный) AccessChecker: тесты проверяют
валидацию ввода, а не ACL. ACL-гейт search_many2many — в integration/security.
"""

import pytest

from tests.conftest import auto

pytestmark = [pytest.mark.integration, pytest.mark.api]


from backend.base.crm.users.models.users import User
from backend.base.crm.security.models.roles import Role

INJECTION_NAME = (
    'id" = 1 OR (SELECT COUNT(*) FROM "user" '
    "WHERE password_hash > '') > 0 OR \"id"
)

_seq = 0


def _uniq(prefix: str) -> str:
    global _seq
    _seq += 1
    return f"{prefix}_{_seq}"


async def _lang_id() -> int:
    from backend.base.crm.languages.models.language import Language

    found = await Language.search(filter=[("code", "=", "en")], limit=1)
    if found:
        return found[0].id
    return await Language.create(
        Language(code="en", name="English", active=True)
    )


async def _make_user() -> int:
    return await User.create(
        User(
            name="Inj User",
            login=_uniq("inj_user"),
            password_hash="secret_hash_value",
            password_salt="secret_salt_value",
            lang_id=await _lang_id(),
        )
    )


async def _make_role() -> int:
    return await Role.create(Role(code=_uniq("inj_role"), name="Inj Role"))


def _assert_filter_rejected(response, field: str):
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "#FILTER_INVALID"
    # detail = "Unknown or private filter field: {name!r}" — сравниваем с repr,
    # т.к. у инъекционного имени внутренние кавычки экранируются.
    assert repr(field) in body["detail"]


# ---------------------------------------------------------------------
# filter в POST /auto/<model>/search
# ---------------------------------------------------------------------


class TestSearchFilterInjection:
    async def test_field_name_injection_rejected(self, authenticated_client):
        client, _, _ = authenticated_client
        response = await client.post(
            auto("/partners/search"),
            json={"fields": ["id"], "filter": [[INJECTION_NAME, "=", 1]]},
        )
        _assert_filter_rejected(response, INJECTION_NAME)

    async def test_unknown_field_in_filter_rejected(
        self, authenticated_client
    ):
        client, _, _ = authenticated_client
        response = await client.post(
            auto("/partners/search"),
            json={"fields": ["id"], "filter": [["no_such_column", "=", 1]]},
        )
        _assert_filter_rejected(response, "no_such_column")

    async def test_private_field_in_filter_rejected(
        self, authenticated_client
    ):
        """Нет подбора хэша операторами сравнения."""
        client, _, _ = authenticated_client
        response = await client.post(
            auto("/users/search"),
            json={
                "fields": ["id"],
                "filter": [["password_hash", ">", "$2b$12$"]],
            },
        )
        _assert_filter_rejected(response, "password_hash")

    async def test_private_field_nested_in_filter_rejected(
        self, authenticated_client
    ):
        client, _, _ = authenticated_client
        response = await client.post(
            auto("/users/search"),
            json={
                "fields": ["id"],
                "filter": [
                    ["name", "=", "x"],
                    "or",
                    [["password_salt", "=", "s"], ["is_admin", "=", False]],
                ],
            },
        )
        _assert_filter_rejected(response, "password_salt")

    async def test_private_field_in_fields_rejected(
        self, authenticated_client
    ):
        """fields — Literal по публичным полям → 422."""
        client, _, _ = authenticated_client
        response = await client.post(
            auto("/users/search"), json={"fields": ["id", "password_hash"]}
        )
        assert response.status_code == 422

    async def test_legit_filter_still_works(self, authenticated_client):
        client, _, _ = authenticated_client
        await User.create(
            User(
                name="Findable",
                login=_uniq("findable"),
                password_hash="h",
                password_salt="s",
                lang_id=await _lang_id(),
            )
        )
        response = await client.post(
            auto("/users/search"),
            json={
                "fields": ["id", "name"],
                "filter": [["name", "=", "Findable"]],
            },
        )
        assert response.status_code == 200
        assert len(response.json()["data"]) >= 1

    async def test_nested_or_filter_allowed(self, authenticated_client):
        client, _, _ = authenticated_client
        response = await client.post(
            auto("/partners/search"),
            json={
                "fields": ["id", "name"],
                "filter": [["name", "=", "A"], "or", ["name", "=", "B"]],
            },
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------
# GET /auto/<model>/search_many2many
# ---------------------------------------------------------------------


class TestSearchMany2manyInjection:
    async def test_sort_injection_neutralized(self, authenticated_client):
        """sort с подзапросом не выполняется: 200, ORDER BY по id."""
        client, _, _ = authenticated_client
        user_id = await _make_user()
        response = await client.get(
            auto("/users/search_many2many"),
            params={
                "id": user_id,
                "name": "role_ids",
                "fields": ["id"],
                "sort": "(SELECT pg_sleep(5))",
            },
        )
        assert response.status_code == 200
        assert isinstance(response.json()["data"], list)

    async def test_private_field_not_leaked(self, authenticated_client):
        client, _, _ = authenticated_client
        role_id = await _make_role()
        user = await User.get(await _make_user())
        await user.update(User(role_ids={"selected": [role_id]}))

        response = await client.get(
            auto("/roles/search_many2many"),
            params={
                "id": role_id,
                "name": "user_ids",
                "fields": ["id", "password_hash"],
            },
        )
        assert response.status_code == 200
        records = response.json()["data"]
        assert len(records) >= 1
        for rec in records:
            assert "password_hash" not in rec
            assert "password_salt" not in rec


# ---------------------------------------------------------------------
# private вне схем; get_public_fields — единый источник
# ---------------------------------------------------------------------


class TestSchemasExcludePrivate:
    def test_public_fields_single_source(self):
        assert "password_hash" in User.get_fields()
        assert "password_hash" not in User.get_public_fields()
        assert "password_salt" not in User.get_public_fields()
        assert "name" in User.get_public_fields()

    async def test_private_absent_from_schemas(self, authenticated_client):
        # authenticated_client поднимает приложение → schema_registry.build_all
        from backend.base.system.dotorm_crud_auto.schema_registry import (
            schema_registry,
        )

        for get in (
            schema_registry.get_base_schema,
            schema_registry.get_create_schema,
            schema_registry.get_update_schema,
        ):
            assert "password_hash" not in get(User).model_fields
            assert "password_salt" not in get(User).model_fields


# ---------------------------------------------------------------------
# FilterParser: белый список имён (без БД)
# ---------------------------------------------------------------------


class TestFilterParserWhitelist:
    def _parser(self, fields=None):
        from backend.base.system.dotorm.dotorm.components.filter_parser import (
            FilterParser,
        )
        from backend.base.system.dotorm.dotorm.components.dialect import (
            POSTGRES,
        )

        return FilterParser(POSTGRES, fields)

    def test_injection_name_rejected(self):
        with pytest.raises(ValueError):
            self._parser(User.get_fields()).parse((INJECTION_NAME, "=", 1))

    def test_unknown_name_rejected(self):
        with pytest.raises(ValueError):
            self._parser(User.get_fields()).parse(("no_such_column", "=", 1))

    def test_private_field_rejected(self):
        """private-поле есть в модели, но в WHERE не допускается."""
        with pytest.raises(ValueError):
            self._parser(User.get_fields()).parse(("password_hash", ">", "x"))

    def test_known_field_passes(self):
        clause, values = self._parser(User.get_fields()).parse(
            ("name", "=", "John")
        )
        assert clause == '"name" = %s'
        assert values == ("John",)

    def test_builder_rejects_injection_name(self):
        """Builder модели передаёт парсеру полную карту полей → отказ."""
        with pytest.raises(ValueError):
            User._builder.build_search(
                fields=["id"], filter=[[INJECTION_NAME, "=", 1]]
            )

    def test_builder_rejects_unknown_name_in_nested_group(self):
        with pytest.raises(ValueError):
            User._builder.build_search(
                fields=["id"],
                filter=[["name", "=", "x"], "or", [["nope", "=", 1]]],
            )


# ---------------------------------------------------------------------
# build_get_many2many: ORDER BY не инъектится (без БД)
# ---------------------------------------------------------------------


class TestBuildM2mSortGuard:
    def test_malicious_sort_falls_back_to_id(self):
        stmt, _ = User._builder.build_get_many2many(
            1,
            Role,
            "user_role_many2many",
            "role_id",
            "user_id",
            ["id"],
            "desc",
            None,
            None,
            "(SELECT pg_sleep(5))",
            10,
        )
        assert "pg_sleep" not in stmt
        assert "ORDER BY id" in stmt


# ---------------------------------------------------------------------
# M2M unlink затрагивает только владельца
# ---------------------------------------------------------------------


class TestM2mUnlinkScoping:
    async def test_unlink_scoped_to_owner(self, db_pool):
        """unselect роли у одного пользователя НЕ снимает её у другого."""
        role_id = await _make_role()
        user_a = await _make_user()
        user_b = await _make_user()

        await (await User.get(user_a)).update(
            User(role_ids={"selected": [role_id]})
        )
        await (await User.get(user_b)).update(
            User(role_ids={"selected": [role_id]})
        )
        await (await User.get(user_a)).update(
            User(role_ids={"unselected": [role_id]})
        )

        a = await User.get(
            user_a,
            fields=["id", "role_ids"],
            fields_nested={"role_ids": ["id"]},
        )
        b = await User.get(
            user_b,
            fields=["id", "role_ids"],
            fields_nested={"role_ids": ["id"]},
        )

        assert role_id not in [r.id for r in a.role_ids]
        assert role_id in [r.id for r in b.role_ids]
