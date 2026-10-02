"""
Администратор группового чата (chat_member.is_admin): кто им становится и что
он может.

Два правила:
- в группе без админа добавляемый пользователь становится админом. Группу из
  «Нового чата» создаёт пользователь — админ он. Клиентский чат партнёра
  создаёт система — админ первый пользователь: руководитель коннектора,
  взявший лид, нажавший «Создать чат» в карточке;
- последний админ не выходит из чата, не снимает с себя права и не может
  быть удалён: сначала права передают другому участнику.
В личных и record-чатах админа нет — участниками там не управляют.

Приглашать и удалять участников могут не только админы: это права can_invite
и can_remove участника (у админа есть все).

Системный админ — суперпользователь или роль system_admin
(Session.is_system_admin) — управляет группой наравне с её админом. Проверка
одна — MemberMixin.check_permissions. Суперпользователю для этого не нужно
состоять в группе: так админ появляется в группе, оставшейся без него. На
роль действуют правила доступа к строкам: чужую группу она не видит, а в
видимую по команде сначала добавляет себя.

Заодно: добавленный участник получает права чата по умолчанию (раньше — NULL
во всех can_*, и писать он не мог), админ меняет права по умолчанию (раньше
PATCH /chats/{id} отвечал 403 любому).

Ручки зовутся под настоящими ролями и правилами (post_init, как в
security-тестах), состав чата проверяется SQL-запросом мимо ORM.

Run: pytest tests/integration/chat/test_chat_admins.py -v -m integration
"""

from types import SimpleNamespace

import pytest
import pytest_asyncio

from backend.base.crm.chat.models.chat import Chat
from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.crm.chat.models.chat_external_chat import ChatExternalChat
from backend.base.crm.leads.models.leads import Lead
from backend.base.crm.leads.models.team_crm import TeamCrm
from backend.base.crm.users.models.users import User
from backend.base.system.dotorm.dotorm.access import AccessDenied
from tests.integration.chat.conftest import auth_headers, create_group
from tests.integration.security.test_field_access import _role_id, as_user

pytestmark = [pytest.mark.integration, pytest.mark.api]

LAST_ADMIN = "CANNOT_REMOVE_THE_LAST_CHAT_ADMIN"


@pytest_asyncio.fixture(autouse=True)
async def _security_init(clean_all_tables):
    from tests.conftest import _run_post_init_once

    await _run_post_init_once()
    yield


@pytest_asyncio.fixture
async def root(user_factory):
    """Суперпользователь (user.is_admin) без ролей: id и заголовки сессии."""
    user = await user_factory(name="Root", login="root", is_admin=True)
    return SimpleNamespace(id=user.id, headers=await auth_headers(user.id))


@pytest_asyncio.fixture
async def role_admin(user_factory):
    """Сотрудник с ролью system_admin, не суперпользователь."""
    user = await user_factory(
        name="Eve",
        login="eve",
        role_ids={
            "selected": [
                await _role_id("base_user"),
                await _role_id("system_admin"),
            ]
        },
    )
    return SimpleNamespace(id=user.id, headers=await auth_headers(user.id))


async def _members(db_pool, chat_id: int) -> dict[int, dict]:
    """Активные участники-пользователи чата: user_id → права."""
    rows = await db_pool.fetch(
        "SELECT user_id, is_admin, can_read, can_write, can_invite, "
        "can_remove FROM chat_member "
        "WHERE chat_id = $1 AND user_id IS NOT NULL AND is_active",
        chat_id,
    )
    return {row["user_id"]: dict(row) for row in rows}


async def _admins(db_pool, chat_id: int) -> set[int]:
    members = await _members(db_pool, chat_id)
    return {uid for uid, perms in members.items() if perms["is_admin"]}


async def _set_permissions(client, chat_id: int, actor, target, **permissions):
    return await client.patch(
        f"/chats/{chat_id}/members/{target.id}/permissions",
        json=permissions,
        headers=actor.headers,
    )


class TestWhoIsAdmin:
    async def test_group_creator_is_admin(self, client, db_pool, staff):
        chat_id = await create_group(client, staff.alice, staff.bob.id)

        assert await _admins(db_pool, chat_id) == {staff.alice.id}

    async def test_direct_chat_has_no_admin(self, client, db_pool, staff):
        resp = await client.post(
            "/chats",
            json={"chat_type": "direct", "user_ids": [staff.bob.id]},
            headers=staff.alice.headers,
        )
        assert resp.status_code == 200, resp.text
        chat_id = resp.json()["data"]["id"]

        assert await _admins(db_pool, chat_id) == set()

    async def test_record_chat_has_no_admin(
        self, db_service, db_pool, partner_factory, staff
    ):
        partner = await partner_factory(name="Клиент")
        chat = await Chat.get_or_create_record_chat(
            "partners", partner.id, staff.alice.id
        )

        assert set(await _members(db_pool, chat.id)) == {staff.alice.id}
        assert await _admins(db_pool, chat.id) == set()

    async def test_first_connector_manager_administers_partner_chat(
        self, db_service, db_pool, partner_factory, staff
    ):
        """Входящее от нового клиента: чат создаёт система, админ — первый
        добавленный руководитель коннектора, второй — обычный участник."""
        partner = await partner_factory(name="Клиент")
        managers = {staff.alice.id, staff.bob.id}
        connector_id = await ChatConnector.create(
            ChatConnector(
                name="Авито", manager_ids={"selected": list(managers)}
            )
        )

        chat = await Chat.get_or_create_partner_chat(
            partner.id, connector=ChatConnector(id=connector_id)
        )

        assert set(await _members(db_pool, chat.id)) == managers
        admins = await _admins(db_pool, chat.id)
        assert len(admins) == 1 and admins < managers

    async def test_partner_card_chat_creator_is_admin(
        self, client, db_service, db_pool, partner_factory, staff
    ):
        """Кнопка «Создать чат» в карточке: чат без руководителей, админ —
        нажавший; следующий вступивший — обычный участник."""
        partner = await partner_factory(name="Клиент")

        resp = await client.post(
            f"/partners/{partner.id}/chat", headers=staff.alice.headers
        )
        assert resp.status_code == 200, resp.text
        chat_id = resp.json()["chat_id"]

        resp = await client.post(
            f"/partners/{partner.id}/chat", headers=staff.bob.headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["chat_id"] == chat_id

        members = await _members(db_pool, chat_id)
        assert set(members) == {staff.alice.id, staff.bob.id}
        assert await _admins(db_pool, chat_id) == {staff.alice.id}

    async def test_lead_taker_becomes_admin_of_partner_chat(
        self, db_service, db_pool, partner_factory, lead_factory, user_factory
    ):
        """Лидогенерация без руководителей: в чате клиента нет
        пользователей, админом становится взявший лид. Берёт его продавец
        под своей сессией: чат клиента он ещё не видит, подписывает сервер."""
        seller = await user_factory(
            name="Dave",
            login="dave",
            role_ids={
                "selected": [
                    await _role_id("base_user"),
                    await _role_id("crm_user"),
                ]
            },
        )
        partner = await partner_factory(name="Клиент")
        connector_id = await ChatConnector.create(ChatConnector(name="Сайт"))
        chat = await Chat.get_or_create_partner_chat(
            partner.id, connector=ChatConnector(id=connector_id)
        )
        await ChatExternalChat.create_link(
            external_id="client-1", connector_id=connector_id, chat_id=chat.id
        )
        created = await lead_factory(
            partner=partner, connector_id=connector_id
        )
        assert await _members(db_pool, chat.id) == {}

        # Как автокруд-роут: запись со связями (search), затем update
        async with as_user(seller):
            lead = await Lead.search_one(
                filter=[("id", "=", created.id)],
                fields=["id", "partner_id", "connector_id"],
            )
            await lead.update(Lead(user_id=User(id=seller.id)), ["user_id"])

        assert await _admins(db_pool, chat.id) == {seller.id}


class TestMemberManagement:
    async def test_added_member_gets_chat_defaults_and_can_write(
        self, client, db_service, db_pool, staff
    ):
        chat_id = await create_group(client, staff.alice, staff.bob.id)

        resp = await client.post(
            f"/chats/{chat_id}/members",
            json={"user_id": staff.carol.id},
            headers=staff.alice.headers,
        )
        assert resp.status_code == 200, resp.text

        carol = (await _members(db_pool, chat_id))[staff.carol.id]
        assert carol["can_read"] is True
        assert carol["can_write"] is True
        assert carol["is_admin"] is False

        resp = await client.post(
            f"/chats/{chat_id}/messages",
            json={"body": "Привет!", "attachments": []},
            headers=staff.carol.headers,
        )
        assert resp.status_code == 200, resp.text

    async def test_regular_member_cannot_add_or_remove(
        self, client, db_pool, staff
    ):
        chat_id = await create_group(client, staff.alice, staff.bob.id)

        resp = await client.post(
            f"/chats/{chat_id}/members",
            json={"user_id": staff.carol.id},
            headers=staff.bob.headers,
        )
        assert resp.status_code == 403
        resp = await client.delete(
            f"/chats/{chat_id}/members/{staff.alice.id}",
            headers=staff.bob.headers,
        )
        assert resp.status_code == 403

        assert set(await _members(db_pool, chat_id)) == {
            staff.alice.id,
            staff.bob.id,
        }

    async def test_admin_removes_member(self, client, db_pool, staff):
        chat_id = await create_group(
            client, staff.alice, staff.bob.id, staff.carol.id
        )

        resp = await client.delete(
            f"/chats/{chat_id}/members/{staff.carol.id}",
            headers=staff.alice.headers,
        )
        assert resp.status_code == 200, resp.text

        assert set(await _members(db_pool, chat_id)) == {
            staff.alice.id,
            staff.bob.id,
        }

    async def test_member_with_can_remove_removes_member(
        self, client, db_pool, staff
    ):
        """Удалять участников — право can_remove; приглашать оно не даёт."""
        chat_id = await create_group(
            client, staff.alice, staff.bob.id, staff.carol.id
        )
        resp = await _set_permissions(
            client, chat_id, staff.alice, staff.bob, can_remove=True
        )
        assert resp.status_code == 200, resp.text

        resp = await client.delete(
            f"/chats/{chat_id}/members/{staff.carol.id}",
            headers=staff.bob.headers,
        )
        assert resp.status_code == 200, resp.text
        resp = await client.post(
            f"/chats/{chat_id}/members",
            json={"user_id": staff.carol.id},
            headers=staff.bob.headers,
        )
        assert resp.status_code == 403

        assert set(await _members(db_pool, chat_id)) == {
            staff.alice.id,
            staff.bob.id,
        }

    async def test_default_can_remove_goes_to_new_members(
        self, client, db_pool, staff
    ):
        chat_id = await create_group(client, staff.alice, staff.bob.id)

        resp = await client.patch(
            f"/chats/{chat_id}",
            json={"default_can_remove": True},
            headers=staff.alice.headers,
        )
        assert resp.status_code == 200, resp.text
        resp = await client.post(
            f"/chats/{chat_id}/members",
            json={"user_id": staff.carol.id},
            headers=staff.alice.headers,
        )
        assert resp.status_code == 200, resp.text

        members = await _members(db_pool, chat_id)
        assert members[staff.carol.id]["can_remove"] is True
        assert members[staff.bob.id]["can_remove"] is False

    async def test_admin_changes_default_permissions(
        self, client, db_pool, staff
    ):
        chat_id = await create_group(client, staff.alice, staff.bob.id)

        resp = await client.patch(
            f"/chats/{chat_id}",
            json={"default_can_invite": True},
            headers=staff.alice.headers,
        )
        assert resp.status_code == 200, resp.text
        resp = await client.patch(
            f"/chats/{chat_id}",
            json={"default_can_invite": False},
            headers=staff.bob.headers,
        )
        assert resp.status_code == 403

        default_can_invite = await db_pool.fetchval(
            "SELECT default_can_invite FROM chat WHERE id = $1", chat_id
        )
        assert default_can_invite is True


class TestLastAdmin:
    """Последний админ не выходит из чата, не снимает с себя права и не
    может быть удалён: сначала права передают другому участнику."""

    async def test_last_admin_leaves_only_after_handover(
        self, client, db_pool, staff
    ):
        chat_id = await create_group(client, staff.alice, staff.bob.id)
        leave = f"/chats/{chat_id}/leave"

        resp = await client.post(leave, headers=staff.alice.headers)
        assert resp.status_code == 400
        assert resp.json()["content"] == LAST_ADMIN
        assert await _admins(db_pool, chat_id) == {staff.alice.id}

        resp = await _set_permissions(
            client, chat_id, staff.alice, staff.bob, is_admin=True
        )
        assert resp.status_code == 200, resp.text
        resp = await client.post(leave, headers=staff.alice.headers)
        assert resp.status_code == 200, resp.text

        assert set(await _members(db_pool, chat_id)) == {staff.bob.id}
        assert await _admins(db_pool, chat_id) == {staff.bob.id}

    async def test_last_admin_cannot_drop_own_rights(
        self, client, db_pool, staff
    ):
        chat_id = await create_group(client, staff.alice, staff.bob.id)

        resp = await _set_permissions(
            client, chat_id, staff.alice, staff.alice, is_admin=False
        )
        assert resp.status_code == 400
        assert resp.json()["content"] == LAST_ADMIN
        assert await _admins(db_pool, chat_id) == {staff.alice.id}

        resp = await _set_permissions(
            client, chat_id, staff.alice, staff.bob, is_admin=True
        )
        assert resp.status_code == 200, resp.text
        resp = await _set_permissions(
            client, chat_id, staff.alice, staff.alice, is_admin=False
        )
        assert resp.status_code == 200, resp.text

        assert await _admins(db_pool, chat_id) == {staff.bob.id}

    async def test_only_member_cannot_leave(self, client, db_pool, staff):
        """Исключения для единственного участника нет: ему остаётся удалить
        чат или добавить коллегу и передать права."""
        chat_id = await create_group(client, staff.alice, staff.bob.id)
        resp = await client.post(
            f"/chats/{chat_id}/leave", headers=staff.bob.headers
        )
        assert resp.status_code == 200, resp.text

        resp = await client.post(
            f"/chats/{chat_id}/leave", headers=staff.alice.headers
        )
        assert resp.status_code == 400
        assert resp.json()["content"] == LAST_ADMIN
        assert await _admins(db_pool, chat_id) == {staff.alice.id}

    async def test_last_admin_cannot_be_removed(self, client, db_pool, staff):
        """Право can_remove не даёт убрать последнего админа."""
        chat_id = await create_group(client, staff.alice, staff.bob.id)
        resp = await _set_permissions(
            client, chat_id, staff.alice, staff.bob, can_remove=True
        )
        assert resp.status_code == 200, resp.text

        resp = await client.delete(
            f"/chats/{chat_id}/members/{staff.alice.id}",
            headers=staff.bob.headers,
        )
        assert resp.status_code == 400
        assert resp.json()["content"] == LAST_ADMIN
        assert await _admins(db_pool, chat_id) == {staff.alice.id}


class TestSystemAdmin:
    """Администратор системы (суперпользователь или роль system_admin)
    управляет группой наравне с её админом. Суперпользователь — любой
    группой, роль — той, что ей видна по правилам доступа."""

    async def test_superuser_manages_group_as_regular_member(
        self, client, db_pool, staff, root
    ):
        """Суперпользователя добавили в группу обычным участником — название,
        права по умолчанию и права участников он меняет всё равно."""
        chat_id = await create_group(
            client, staff.alice, staff.bob.id, root.id
        )

        resp = await client.patch(
            f"/chats/{chat_id}",
            json={"name": "Продажи", "default_can_invite": True},
            headers=root.headers,
        )
        assert resp.status_code == 200, resp.text
        resp = await _set_permissions(
            client, chat_id, root, staff.bob, can_remove=True
        )
        assert resp.status_code == 200, resp.text

        chat = await db_pool.fetchrow(
            "SELECT name, default_can_invite FROM chat WHERE id = $1", chat_id
        )
        assert dict(chat) == {"name": "Продажи", "default_can_invite": True}
        members = await _members(db_pool, chat_id)
        assert members[staff.bob.id]["can_remove"] is True
        # Админом чата он при этом не стал
        assert await _admins(db_pool, chat_id) == {staff.alice.id}

    async def test_superuser_manages_group_he_is_not_in(
        self, client, db_service, db_pool, staff, root
    ):
        """Не участник: добавляет и удаляет людей, удаляет и возвращает чат —
        и сам участником не становится."""
        chat_id = await create_group(client, staff.alice, staff.bob.id)
        members_url = f"/chats/{chat_id}/members"

        resp = await client.post(
            members_url, json={"user_id": staff.carol.id}, headers=root.headers
        )
        assert resp.status_code == 200, resp.text
        resp = await client.delete(
            f"{members_url}/{staff.bob.id}", headers=root.headers
        )
        assert resp.status_code == 200, resp.text
        assert set(await _members(db_pool, chat_id)) == {
            staff.alice.id,
            staff.carol.id,
        }

        resp = await client.delete(f"/chats/{chat_id}", headers=root.headers)
        assert resp.status_code == 200, resp.text
        active = "SELECT active FROM chat WHERE id = $1"
        assert await db_pool.fetchval(active, chat_id) is False
        resp = await client.post(
            f"/chats/{chat_id}/restore", headers=root.headers
        )
        assert resp.status_code == 200, resp.text
        assert await db_pool.fetchval(active, chat_id) is True

    async def test_superuser_appoints_admin_in_group_without_admin(
        self, client, db_pool, staff, root
    ):
        """Группа без админа — в старых базах такие остались. Изнутри её не
        починить: права раздавать некому. Суперпользователь назначает
        админа, дальше тот управляет сам."""
        chat_id = await create_group(client, staff.alice, staff.bob.id)
        await db_pool.execute(
            "UPDATE chat_member SET is_admin = false, can_invite = false, "
            "can_remove = false WHERE chat_id = $1",
            chat_id,
        )

        resp = await _set_permissions(
            client, chat_id, staff.alice, staff.bob, is_admin=True
        )
        assert resp.status_code == 403

        resp = await _set_permissions(
            client, chat_id, root, staff.bob, is_admin=True
        )
        assert resp.status_code == 200, resp.text
        assert await _admins(db_pool, chat_id) == {staff.bob.id}

        resp = await client.patch(
            f"/chats/{chat_id}",
            json={"default_can_invite": True},
            headers=staff.bob.headers,
        )
        assert resp.status_code == 200, resp.text

    async def test_member_added_by_superuser_to_group_without_admin_is_admin(
        self, client, db_service, db_pool, staff, root
    ):
        """Второй путь для группы без админа: добавленный в неё пользователь
        становится админом — кто бы его ни добавил."""
        chat_id = await create_group(client, staff.alice, staff.bob.id)
        await db_pool.execute(
            "UPDATE chat_member SET is_admin = false WHERE chat_id = $1",
            chat_id,
        )

        resp = await client.post(
            f"/chats/{chat_id}/members",
            json={"user_id": staff.carol.id},
            headers=root.headers,
        )
        assert resp.status_code == 200, resp.text

        assert await _admins(db_pool, chat_id) == {staff.carol.id}

    async def test_role_manages_group_as_regular_member(
        self, client, db_pool, staff, role_admin
    ):
        """Роль system_admin в группе — обычный участник, но настройки и
        права участников меняет."""
        chat_id = await create_group(
            client, staff.alice, staff.bob.id, role_admin.id
        )

        resp = await client.patch(
            f"/chats/{chat_id}",
            json={"default_can_invite": True},
            headers=role_admin.headers,
        )
        assert resp.status_code == 200, resp.text
        resp = await _set_permissions(
            client, chat_id, role_admin, staff.bob, can_remove=True
        )
        assert resp.status_code == 200, resp.text

        default_can_invite = await db_pool.fetchval(
            "SELECT default_can_invite FROM chat WHERE id = $1", chat_id
        )
        assert default_can_invite is True
        members = await _members(db_pool, chat_id)
        assert members[staff.bob.id]["can_remove"] is True
        assert await _admins(db_pool, chat_id) == {staff.alice.id}

    async def test_role_does_not_see_foreign_group(
        self, client, db_pool, staff, role_admin
    ):
        """Полный доступ в ORM — только у суперпользователя: чужую группу
        роль не видит и не меняет. Проверку прав она проходит, но чтение
        чата ORM ей запрещает: в приложении это ответ 403, тестовый клиент
        отдаёт само исключение."""
        chat_id = await create_group(client, staff.alice, staff.bob.id)

        with pytest.raises(AccessDenied):
            await client.patch(
                f"/chats/{chat_id}",
                json={"default_can_invite": True},
                headers=role_admin.headers,
            )

        default_can_invite = await db_pool.fetchval(
            "SELECT default_can_invite FROM chat WHERE id = $1", chat_id
        )
        assert default_can_invite is False

    async def test_role_joins_group_visible_by_team(
        self, client, db_service, db_pool, staff, role_admin
    ):
        """Группу своей команды роль читает, но менять может, только став
        участником: правила строк пускают к записи участников чата (иначе
        AccessDenied — в приложении ответ 403). Добавить участником она
        может и себя."""
        team_id = await TeamCrm.create(
            TeamCrm(name="Продажи", user_ids={"selected": [role_admin.id]})
        )
        chat_id = await create_group(client, staff.alice, staff.bob.id)
        await db_pool.execute(
            "UPDATE chat SET team_id = $1 WHERE id = $2", team_id, chat_id
        )
        settings = {"default_can_invite": True}

        with pytest.raises(AccessDenied):
            await client.patch(
                f"/chats/{chat_id}", json=settings, headers=role_admin.headers
            )

        resp = await client.post(
            f"/chats/{chat_id}/members",
            json={"user_id": role_admin.id},
            headers=role_admin.headers,
        )
        assert resp.status_code == 200, resp.text
        resp = await client.patch(
            f"/chats/{chat_id}", json=settings, headers=role_admin.headers
        )
        assert resp.status_code == 200, resp.text

        assert set(await _members(db_pool, chat_id)) == {
            staff.alice.id,
            staff.bob.id,
            role_admin.id,
        }
