"""
Чат по значку контакта (issue #47) и визард создания чата.

Значок мессенджера/email у контакта ведёт в чат собеседника: у клиента —
единственный внешний чат партнёра, у сотрудника — личный чат с текущим
пользователем. Чата нет — открывается визард с этим собеседником, создаёт
пользователь кнопкой. Ручки:

- GET /contacts/{id}/chat — чат по контакту без создания;
- GET /chats/members?kind=users|partners — кандидаты в участники (вкладки
  «Пользователи» и «Партнёры» визарда) с chat_id уже существующего чата
  (бейдж «есть чат»);
- POST /chats с партнёром помечает чат внешним (is_internal=false): иначе
  он прятался в «Сотрудниках», а у партнёра плодились чаты;
- GET /chats/{id}/connectors отдаёт contact_type_id — по нему страница чата
  подставляет канал контакта, со значка которого пришли.

Ручки зовутся под настоящими ролями и правилами (post_init, как в
test_chat_admins), состав чатов проверяется SQL-запросом мимо ORM.

Run: pytest tests/integration/chat/test_contact_chat.py -v -m integration
"""

import pytest
import pytest_asyncio

from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.crm.partners.models.contact import Contact
from backend.base.crm.partners.models.contact_type import ContactType
from backend.base.crm.partners.models.partners import Partner
from backend.base.crm.users.models.users import User
from tests.integration.chat.conftest import create_group

pytestmark = [pytest.mark.integration, pytest.mark.api]


@pytest_asyncio.fixture(autouse=True)
async def _security_init(clean_all_tables):
    from tests.conftest import _run_post_init_once

    await _run_post_init_once()
    yield


@pytest_asyncio.fixture
async def contact_type() -> int:
    """Свой тип контакта — не зависит от сидов partners."""
    return await ContactType.create(ContactType(name="im_test", label="IM"))


async def _contact(
    contact_type: int,
    value: str,
    *,
    partner_id: int | None = None,
    user_id: int | None = None,
) -> int:
    """Контакт партнёра или сотрудника; name = value, как пишет виджет."""
    return await Contact.create(
        Contact(
            name=value,
            value=value,
            contact_type_id=ContactType(id=contact_type),
            partner_id=Partner(id=partner_id) if partner_id else None,
            user_id=User(id=user_id) if user_id else None,
        )
    )


async def _resolve(client, contact_id: int, actor) -> dict:
    resp = await client.get(
        f"/contacts/{contact_id}/chat", headers=actor.headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _members(client, actor, kind: str, search: str = "") -> list[dict]:
    resp = await client.get(
        "/chats/members",
        params={"kind": kind, "search": search},
        headers=actor.headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _create_direct(client, actor, user_id: int) -> int:
    resp = await client.post(
        "/chats",
        json={"chat_type": "direct", "user_ids": [user_id]},
        headers=actor.headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _create_partner_group(client, actor, partner_id: int, name: str):
    return await client.post(
        "/chats",
        json={
            "name": name,
            "chat_type": "group",
            "user_ids": [],
            "partner_ids": [partner_id],
        },
        headers=actor.headers,
    )


class TestResolveContactChat:
    """GET /contacts/{id}/chat — чат собеседника по его контакту."""

    async def test_partner_contact_without_chat(
        self, client, db_service, partner_factory, staff, contact_type
    ):
        partner = await partner_factory(name="Клиент")
        contact_id = await _contact(
            contact_type, "client@example.com", partner_id=partner.id
        )

        found = await _resolve(client, contact_id, staff.alice)

        assert found == {
            "chat_id": None,
            "partner_id": partner.id,
            "user_id": None,
            "name": "Клиент",
        }

    async def test_partner_contact_finds_partner_chat(
        self, client, db_service, partner_factory, staff, contact_type
    ):
        """Чат партнёра один (модель 1:1): созданный кнопкой «Создать чат»
        в карточке находится по любому контакту партнёра."""
        partner = await partner_factory(name="Клиент")
        mail = await _contact(
            contact_type, "a@example.com", partner_id=partner.id
        )
        phone = await _contact(
            contact_type, "+79990000001", partner_id=partner.id
        )
        resp = await client.post(
            f"/partners/{partner.id}/chat", headers=staff.alice.headers
        )
        assert resp.status_code == 200, resp.text
        chat_id = resp.json()["chat_id"]

        assert (await _resolve(client, mail, staff.alice))[
            "chat_id"
        ] == chat_id
        assert (await _resolve(client, phone, staff.bob))["chat_id"] == chat_id

    async def test_user_contact_direct_chat(
        self, client, db_service, staff, contact_type
    ):
        """Контакт сотрудника: личный чат с ТЕКУЩИМ пользователем — у Алисы
        и Кэрол он разный."""
        contact_id = await _contact(
            contact_type, "@bob_im", user_id=staff.bob.id
        )

        found = await _resolve(client, contact_id, staff.alice)
        assert found == {
            "chat_id": None,
            "partner_id": None,
            "user_id": staff.bob.id,
            "name": "Bob",
        }

        chat_id = await _create_direct(client, staff.alice, staff.bob.id)

        assert (await _resolve(client, contact_id, staff.alice))[
            "chat_id"
        ] == chat_id
        assert (await _resolve(client, contact_id, staff.carol))[
            "chat_id"
        ] is None

    async def test_own_contact_is_nobody(
        self, client, db_service, staff, contact_type
    ):
        contact_id = await _contact(
            contact_type, "@alice_im", user_id=staff.alice.id
        )

        found = await _resolve(client, contact_id, staff.alice)

        assert found == {
            "chat_id": None,
            "partner_id": None,
            "user_id": None,
            "name": None,
        }

    async def test_unknown_contact_is_404(self, client, db_service, staff):
        resp = await client.get(
            "/contacts/999999/chat", headers=staff.alice.headers
        )

        assert resp.status_code == 404


class TestSearchChatMembers:
    """GET /chats/members — кандидаты в участники с chat_id уже существующего
    чата: по нему визард показывает бейдж «есть чат» и открывает чат."""

    async def test_users_by_name_with_direct_chat(
        self, client, db_service, staff
    ):
        before = await _members(client, staff.alice, "users", "bob")
        assert [u["name"] for u in before] == ["Bob"]
        assert before[0]["chat_id"] is None

        chat_id = await _create_direct(client, staff.alice, staff.bob.id)

        after = await _members(client, staff.alice, "users", "bob")
        assert after[0]["id"] == staff.bob.id
        assert after[0]["chat_id"] == chat_id
        # Личный чат Алисы с Бобом — не чат Кэрол
        for_carol = await _members(client, staff.carol, "users", "bob")
        assert for_carol[0]["chat_id"] is None

    async def test_users_found_by_contact_value(
        self, client, db_service, staff, contact_type
    ):
        """Сотрудника находят и по его контакту: в имени «Bob» значения
        «@bob_im» нет."""
        await _contact(contact_type, "@bob_im", user_id=staff.bob.id)

        found = await _members(client, staff.alice, "users", "bob_im")

        assert [u["id"] for u in found] == [staff.bob.id]
        assert await _members(client, staff.alice, "users", "nobody_xyz") == []

    async def test_partners_are_partner_contacts_only(
        self, client, db_service, partner_factory, staff, contact_type
    ):
        """Сотрудников во вкладке «Партнёры» нет (они в «Пользователях»),
        неактивные контакты тоже; у партнёра с чатом — его chat_id."""
        partner = await partner_factory(name="Клиент")
        contact_id = await _contact(
            contact_type, "client@example.com", partner_id=partner.id
        )
        await _contact(contact_type, "@bob_im", user_id=staff.bob.id)
        inactive = await _contact(
            contact_type, "old@example.com", partner_id=partner.id
        )
        await Contact(id=inactive).update(Contact(active=False), ["active"])

        found = await _members(client, staff.alice, "partners")
        assert found == [
            {
                "id": contact_id,
                "name": "client@example.com",
                "partner_id": partner.id,
                "partner_name": "Клиент",
                "chat_id": None,
            }
        ]

        resp = await client.post(
            f"/partners/{partner.id}/chat", headers=staff.alice.headers
        )
        assert resp.status_code == 200, resp.text
        chat_id = resp.json()["chat_id"]

        found = await _members(client, staff.bob, "partners")
        assert [c["chat_id"] for c in found] == [chat_id]

    async def test_partners_found_by_value_or_partner_name(
        self, client, db_service, partner_factory, staff, contact_type
    ):
        """Поиск — по значению контакта ИЛИ по имени клиента: contact.name
        это email/телефон, имени клиента в нём нет."""
        romashka = await partner_factory(name="Ромашка")
        vasilek = await partner_factory(name="Василёк")
        by_mail = await _contact(
            contact_type, "info@romashka.ru", partner_id=romashka.id
        )
        by_partner = await _contact(
            contact_type, "+79990000002", partner_id=vasilek.id
        )

        assert [
            c["id"]
            for c in await _members(
                client, staff.alice, "partners", "romashka"
            )
        ] == [by_mail]
        assert [
            c["id"]
            for c in await _members(client, staff.alice, "partners", "Васил")
        ] == [by_partner]
        assert (
            await _members(client, staff.alice, "partners", "nobody_xyz") == []
        )

    async def test_kind_is_required_and_validated(
        self, client, db_service, staff
    ):
        resp = await client.get("/chats/members", headers=staff.alice.headers)
        assert resp.status_code == 422
        resp = await client.get(
            "/chats/members",
            params={"kind": "all"},
            headers=staff.alice.headers,
        )
        assert resp.status_code == 422


class TestPartnerChatFromWizard:
    """POST /chats с партнёром — чат клиента, а не внутренний."""

    async def test_group_with_partner_is_external(
        self, client, db_service, db_pool, partner_factory, staff
    ):
        partner = await partner_factory(name="Клиент")

        resp = await _create_partner_group(
            client, staff.alice, partner.id, "Клиент"
        )
        assert resp.status_code == 200, resp.text
        chat_id = resp.json()["data"]["id"]
        assert resp.json()["data"]["is_internal"] is False

        is_internal = await db_pool.fetchval(
            "SELECT is_internal FROM chat WHERE id = $1", chat_id
        )
        assert is_internal is False
        # Раздел «Клиенты», а не «Сотрудники»
        resp = await client.get(
            "/chats",
            params={"section": "partners"},
            headers=staff.alice.headers,
        )
        assert resp.status_code == 200, resp.text
        assert [c["id"] for c in resp.json()["data"]] == [chat_id]
        # Карточка партнёра и значок контакта его видят
        resp = await client.get(
            f"/records/partners/{partner.id}/partner_chat",
            headers=staff.alice.headers,
        )
        assert resp.json()["chat_id"] == chat_id

    async def test_second_partner_chat_is_refused(
        self, client, db_service, partner_factory, staff
    ):
        partner = await partner_factory(name="Клиент")
        resp = await _create_partner_group(
            client, staff.alice, partner.id, "Первый"
        )
        assert resp.status_code == 200, resp.text

        resp = await _create_partner_group(
            client, staff.bob, partner.id, "Второй"
        )

        assert resp.status_code == 400
        assert resp.json()["content"] == "PARTNER_CHAT_EXISTS"

    async def test_group_without_partner_stays_internal(
        self, client, db_service, db_pool, staff
    ):
        chat_id = await create_group(client, staff.alice, staff.bob.id)

        is_internal = await db_pool.fetchval(
            "SELECT is_internal FROM chat WHERE id = $1", chat_id
        )
        assert is_internal is True


class TestConnectorsContactType:
    async def test_connectors_carry_contact_type(
        self, client, db_service, staff, contact_type
    ):
        """По contact_type_id страница чата подставляет канал контакта, со
        значка которого открыли чат; у внутреннего канала типа нет."""
        await _contact(contact_type, "@bob_im", user_id=staff.bob.id)
        connector_id = await ChatConnector.create(
            ChatConnector(
                name="Мессенджер", contact_type_id=ContactType(id=contact_type)
            )
        )
        group = await create_group(client, staff.alice, staff.bob.id)

        resp = await client.get(
            f"/chats/{group}/connectors", headers=staff.alice.headers
        )
        assert resp.status_code == 200, resp.text

        by_id = {
            c["connector_id"]: c["contact_type_id"]
            for c in resp.json()["data"]
        }
        assert by_id == {None: None, connector_id: contact_type}
