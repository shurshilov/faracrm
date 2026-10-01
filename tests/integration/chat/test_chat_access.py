"""
Доступ в чате — то, что проверяют сами ручки, а не только правила ORM:

- сообщение правят, удаляют и закрепляют только в его чате: права проверяются
  в чате из адреса, поэтому сообщение другого чата по этому адресу — 404
  (раньше админ своей группы правил сообщения любого чата, где состоит);
- заметки записи (record-чат) открывает тот, кто видит саму запись (раньше —
  любой сотрудник для любой записи);
- ленту читают участники, команда чата и суперпользователь, остальным — 403
  (раньше суперпользователь в чужом чате получал 500);
- пересылка подписывает сообщение именем автора (раньше — 500);
- сообщение, не ушедшее во внешний канал, остаётся в ленте с send_failed;
- коннектор уведомлений (Web Push) каналом переписки не предлагается;
- коннекторы сотрудник только читает, настраивает их администратор настроек.

Как в test_chat_admins: настоящие роли и правила (post_init), данные
готовятся до первого запроса, результат проверяется SQL-запросом мимо ORM.

Run: pytest tests/integration/chat/test_chat_access.py -v -m integration
"""

import pytest
import pytest_asyncio

from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.crm.partners.models.contact import Contact
from backend.base.crm.partners.models.contact_type import ContactType
from backend.base.crm.users.models.users import User
from backend.base.system.dotorm.dotorm.access import AccessDenied
from tests.integration.chat.conftest import auth_headers, create_group
from tests.integration.security.test_field_access import _role_id, as_user

pytestmark = [pytest.mark.integration, pytest.mark.api]


@pytest_asyncio.fixture(autouse=True)
async def _security_init(clean_all_tables):
    from tests.conftest import _run_post_init_once

    await _run_post_init_once()
    yield


async def _post(client, chat_id: int, author, body: str, **extra) -> dict:
    resp = await client.post(
        f"/chats/{chat_id}/messages",
        json={"body": body, "attachments": [], **extra},
        headers=author.headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


class TestMessageBelongsToChat:
    async def test_message_of_another_chat_is_not_found(
        self, client, db_service, db_pool, staff
    ):
        """Алиса — админ своей группы и обычный участник группы Кэрол.
        Через адрес своей группы сообщение Кэрол ей не достать."""
        own = await create_group(client, staff.alice, staff.bob.id)
        foreign = await create_group(client, staff.carol, staff.alice.id)
        message = await _post(client, foreign, staff.carol, "Отчёт готов")
        url = f"/chats/{own}/messages/{message['id']}"

        resp = await client.patch(
            url, json={"body": "Исправлено"}, headers=staff.alice.headers
        )
        assert resp.status_code == 404
        resp = await client.delete(url, headers=staff.alice.headers)
        assert resp.status_code == 404
        resp = await client.post(
            f"{url}/pin", json={"pinned": True}, headers=staff.alice.headers
        )
        assert resp.status_code == 404

        row = await db_pool.fetchrow(
            "SELECT body, is_deleted, pinned FROM chat_message WHERE id = $1",
            message["id"],
        )
        assert dict(row) == {
            "body": "Отчёт готов",
            "is_deleted": False,
            "pinned": False,
        }


class TestRecordChat:
    """Заметки записи открывает тот, кто видит запись. Запись здесь —
    групповой чат: участник его видит, посторонний — нет."""

    async def test_notes_follow_record_access(self, client, db_service, staff):
        group = await create_group(client, staff.alice, staff.bob.id)
        url = f"/records/chat/{group}/chat"

        resp = await client.post(url, headers=staff.carol.headers)
        assert resp.status_code == 403
        resp = await client.post(url, headers=staff.bob.headers)
        assert resp.status_code == 200, resp.text

    async def test_unknown_record_has_no_notes(
        self, client, db_service, staff
    ):
        resp = await client.post(
            "/records/chat/999999/chat", headers=staff.alice.headers
        )
        assert resp.status_code == 403
        resp = await client.post(
            "/records/no_such_table/1/chat", headers=staff.alice.headers
        )
        assert resp.status_code == 403


class TestReadAccess:
    async def test_outsider_cannot_read_superuser_can(
        self, client, db_service, user_factory, staff
    ):
        root = await user_factory(name="Root", login="root", is_admin=True)
        root_headers = await auth_headers(root.id)
        group = await create_group(client, staff.alice, staff.bob.id)
        await _post(client, group, staff.alice, "Привет")
        url = f"/chats/{group}/messages"

        resp = await client.get(url, headers=staff.carol.headers)
        assert resp.status_code == 403

        resp = await client.get(url, headers=root_headers)
        assert resp.status_code == 200, resp.text
        assert [m["body"] for m in resp.json()["data"]] == ["Привет"]


class TestForward:
    async def test_forward_is_signed_with_author_name(
        self, client, db_service, db_pool, staff
    ):
        source = await create_group(client, staff.alice, staff.bob.id)
        target = await create_group(client, staff.bob, staff.carol.id)
        message = await _post(client, source, staff.alice, "Привет")

        resp = await client.post(
            f"/chats/{source}/messages/{message['id']}/forward",
            json={"target_chat_id": target},
            headers=staff.bob.headers,
        )
        assert resp.status_code == 200, resp.text

        body = await db_pool.fetchval(
            "SELECT body FROM chat_message WHERE id = $1",
            resp.json()["message_id"],
        )
        assert body == "[Forwarded from Alice]\nПривет"


class TestSendFailed:
    async def test_undelivered_message_stays_and_is_marked(
        self, client, db_service, db_pool, staff
    ):
        """У коннектора нет адресата в этом чате: сообщение сохраняется в
        ленте, но помечается как не ушедшее во внешний канал."""
        connector_id = await ChatConnector.create(ChatConnector(name="Сайт"))
        group = await create_group(client, staff.alice, staff.bob.id)

        external = await _post(
            client,
            group,
            staff.alice,
            "Здравствуйте",
            connector_id=connector_id,
        )
        internal = await _post(client, group, staff.alice, "Коллеги, привет")

        assert external["send_failed"] is True
        assert internal["send_failed"] is False
        rows = await db_pool.fetch(
            "SELECT id, send_failed FROM chat_message WHERE chat_id = $1",
            group,
        )
        assert {row["id"]: row["send_failed"] for row in rows} == {
            external["id"]: True,
            internal["id"]: False,
        }


class TestChannels:
    async def test_notification_connector_is_not_a_channel(
        self, client, staff
    ):
        """У Боба есть контакт, под который подходят два коннектора: обычный
        и уведомлений (как Web Push с подпиской). Каналом переписки Алисе
        предлагается только обычный — уведомления рассылает сервер сам."""
        contact_type_id = await ContactType.create(
            ContactType(name="push_test", label="Push")
        )
        await Contact.create(
            Contact(
                name="Подписка Боба",
                value="subscription-1",
                user_id=User(id=staff.bob.id),
                contact_type_id=ContactType(id=contact_type_id),
            )
        )
        messenger_id = await ChatConnector.create(
            ChatConnector(
                name="Мессенджер",
                contact_type_id=ContactType(id=contact_type_id),
            )
        )
        await ChatConnector.create(
            ChatConnector(
                name="Уведомления",
                category="notification",
                contact_type_id=ContactType(id=contact_type_id),
            )
        )
        group = await create_group(client, staff.alice, staff.bob.id)

        resp = await client.get(
            f"/chats/{group}/connectors", headers=staff.alice.headers
        )
        assert resp.status_code == 200, resp.text
        channels = [c["connector_id"] for c in resp.json()["data"]]
        # None — внутренний канал, он есть всегда
        assert channels == [None, messenger_id]


class TestConnectorSettings:
    async def test_employee_reads_but_does_not_change_connector(
        self, user_factory
    ):
        employee = await user_factory(
            name="Dave",
            login="dave",
            role_ids={"selected": [await _role_id("base_user")]},
        )
        connector_id = await ChatConnector.create(ChatConnector(name="Сайт"))

        async with as_user(employee):
            connector = await ChatConnector.search_one(
                filter=[("id", "=", connector_id)], fields=["id", "name"]
            )
            assert connector.name == "Сайт"
            with pytest.raises(AccessDenied):
                await connector.update(ChatConnector(name="Чужой"))
            with pytest.raises(AccessDenied):
                await ChatConnector.create(ChatConnector(name="Свой"))

    async def test_settings_routes_are_for_settings_admin(
        self, client, user_factory, staff
    ):
        admin = await user_factory(
            name="Eve",
            login="eve",
            role_ids={
                "selected": [
                    await _role_id("base_user"),
                    await _role_id("system_admin"),
                ]
            },
        )
        admin_headers = await auth_headers(admin.id)
        connector_id = await ChatConnector.create(ChatConnector(name="Сайт"))

        for action in ("webhook/set", "webhook/unset", "test", "sync-numbers"):
            resp = await client.post(
                f"/connectors/{connector_id}/{action}",
                headers=staff.alice.headers,
            )
            assert resp.status_code == 403, action
            assert resp.json()["content"] == "ADMIN_REQUIRED"

        # У внутреннего коннектора проверки соединения нет — важно, что
        # администратора настроек ручка пускает.
        resp = await client.post(
            f"/connectors/{connector_id}/test", headers=admin_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["ok"] is False
