"""
Integration tests for Chat module.

Tests cover:
- Chat CRUD
- Chat members
- Chat messages
- Chat connectors

Run: pytest tests/integration/chat/test_chat.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration
from backend.base.crm.chat.models.chat import Chat
from backend.base.crm.chat.models.chat_message import ChatMessage
from backend.base.crm.security.models.sessions import Session


class TestChatCreate:
    """Tests for Chat model."""

    async def test_create_chat(self):

        cid = await Chat.create(Chat(name="Support Chat"))
        c = await Chat.get(cid)
        assert c.name == "Support Chat"

    async def test_create_chat_with_type(self):

        cid = await Chat.create(
            Chat(
                name="Private Chat",
                chat_type="private",
            )
        )
        c = await Chat.get(cid)
        assert c.chat_type == "private"

    async def test_search_chats(self):

        await Chat.create(Chat(name="Chat A"))
        await Chat.create(Chat(name="Chat B"))
        await Chat.create(Chat(name="Chat C"))
        chats = await Chat.search(fields=["id", "name"])
        assert len(chats) == 3


class TestChatMessages:
    """Tests for ChatMessage model."""

    async def test_create_message(self):

        cid = await Chat.create(Chat(name="Msg Chat"))
        mid = await ChatMessage.create(
            ChatMessage(
                chat_id=cid,
                body="Hello, world!",
            )
        )
        m = await ChatMessage.get(mid)
        assert m.body == "Hello, world!"

    async def test_search_messages_by_chat(self):

        c1 = await Chat.create(Chat(name="Chat 1"))
        c2 = await Chat.create(Chat(name="Chat 2"))

        await ChatMessage.create(ChatMessage(chat_id=c1, body="Msg 1"))
        await ChatMessage.create(ChatMessage(chat_id=c1, body="Msg 2"))
        await ChatMessage.create(ChatMessage(chat_id=c2, body="Msg 3"))

        msgs = await ChatMessage.search(
            fields=["id", "body"],
            filter=[("chat_id", "=", c1)],
        )
        assert len(msgs) == 2

    async def test_message_ordering(self):

        cid = await Chat.create(Chat(name="Order Chat"))
        for i in range(5):
            await ChatMessage.create(
                ChatMessage(
                    chat_id=cid,
                    body=f"Message {i}",
                )
            )

        msgs = await ChatMessage.search(
            fields=["id", "body"],
            filter=[("chat_id", "=", cid)],
            sort="id",
            order="asc",
        )
        assert len(msgs) == 5
        assert msgs[0].body == "Message 0"
        assert msgs[-1].body == "Message 4"


class TestChatDelete:
    """Tests for deleting chats."""

    async def test_delete_chat(self):

        cid = await Chat.create(Chat(name="Delete Me"))
        c = await Chat.get(cid)
        await c.delete()
        assert await Chat.get_or_none(cid) is None

    async def test_delete_message(self):

        cid = await Chat.create(Chat(name="Msg Del Chat"))
        mid = await ChatMessage.create(
            ChatMessage(chat_id=cid, body="Delete this")
        )
        m = await ChatMessage.get(mid)
        await m.delete()
        assert await ChatMessage.get_or_none(mid) is None


class TestChatVisibilityFilters:
    """
    Tests for GET /chats visibility flags:
      include_deleted — show soft-deleted chats (any user)
      include_record  — show record chats (any user)
      include_foreign — bypass membership check (admin only, else 403)

    By default every user — including is_admin — sees only their own
    active, non-record chats.
    """

    @staticmethod
    async def _login(client, user_factory, *, is_admin: bool, login: str):
        """Create a user and authenticated session; return (client, user_id)."""
        import secrets
        from datetime import datetime, timedelta, timezone

        user = await user_factory(
            name=f"Test {login}", login=login, is_admin=is_admin
        )
        token = secrets.token_urlsafe(64)
        cookie_token = secrets.token_urlsafe(64)
        await Session.create(
            Session(
                user_id=user.id,
                token=token,
                cookie_token=cookie_token,
                ttl=3600,
                expired_datetime=datetime.now(timezone.utc)
                + timedelta(hours=1),
                create_user_id=user.id,
                update_user_id=user.id,
                active=True,
            )
        )
        client.headers["Authorization"] = f"Bearer {token}"
        client.cookies.set("session_cookie", cookie_token)
        return user.id

    @staticmethod
    async def _mk_chat(
        name: str,
        *,
        member_user_ids: list[int],
        chat_type: str = "group",
        active: bool = True,
        res_model: str | None = None,
        res_id: int | None = None,
        inactive_member_user_ids: list[int] | None = None,
    ) -> int:
        """
        Create chat + active members + optionally inactive members.

        inactive_member_user_ids simulates the soft-leave case
        (user was a member but left — chat_member.is_active=false).
        """

        payload = Chat(name=name, chat_type=chat_type, active=active)
        if res_model is not None:
            payload.res_model = res_model
        if res_id is not None:
            payload.res_id = res_id

        chat_id = await Chat.create(payload)
        chat = await Chat.get(chat_id)

        for uid in member_user_ids:
            await chat.add_member(uid)

        if inactive_member_user_ids:
            for uid in inactive_member_user_ids:
                await chat.add_member(uid)
                await chat.remove_member(uid)  # soft — is_active=false

        return chat_id

    async def test_regular_user_sees_only_own_active_non_record(
        self, client, user_factory
    ):
        alice_id = await self._login(
            client, user_factory, is_admin=False, login="alice"
        )
        # Pre-create the other user separately (no session swap needed)
        bob = await user_factory(name="Bob", login="bob", is_admin=False)

        own = await self._mk_chat("own", member_user_ids=[alice_id])
        deleted = await self._mk_chat(
            "own-deleted", member_user_ids=[alice_id], active=False
        )
        record = await self._mk_chat(
            "own-record",
            member_user_ids=[alice_id],
            chat_type="record",
            res_model="lead",
            res_id=1,
        )
        foreign = await self._mk_chat("foreign", member_user_ids=[bob.id])
        left = await self._mk_chat(
            "left",
            member_user_ids=[bob.id],
            inactive_member_user_ids=[alice_id],
        )

        resp = await client.get("/chats")
        assert resp.status_code == 200, resp.text
        ids = {c["id"] for c in resp.json()["data"]}
        assert own in ids
        assert deleted not in ids
        assert record not in ids
        assert foreign not in ids
        assert left not in ids  # inactive membership == not a member

    async def test_include_deleted_shows_soft_deleted(
        self, client, user_factory
    ):
        alice_id = await self._login(
            client, user_factory, is_admin=False, login="alice"
        )
        own = await self._mk_chat("own", member_user_ids=[alice_id])
        deleted = await self._mk_chat(
            "own-deleted", member_user_ids=[alice_id], active=False
        )

        resp = await client.get("/chats", params={"include_deleted": 1})
        assert resp.status_code == 200
        ids = {c["id"] for c in resp.json()["data"]}
        assert own in ids
        assert deleted in ids  # now visible

    async def test_include_record_shows_record_chats(
        self, client, user_factory
    ):
        alice_id = await self._login(
            client, user_factory, is_admin=False, login="alice"
        )
        own = await self._mk_chat("own", member_user_ids=[alice_id])
        record = await self._mk_chat(
            "own-record",
            member_user_ids=[alice_id],
            chat_type="record",
            res_model="lead",
            res_id=1,
        )

        resp = await client.get("/chats", params={"include_record": 1})
        assert resp.status_code == 200
        ids = {c["id"] for c in resp.json()["data"]}
        assert own in ids
        assert record in ids

    async def test_include_record_still_hides_foreign_for_regular(
        self, client, user_factory
    ):
        """include_record does NOT grant access to someone else's record chat."""
        alice_id = await self._login(
            client, user_factory, is_admin=False, login="alice"
        )
        bob = await user_factory(name="Bob", login="bob", is_admin=False)

        foreign_record = await self._mk_chat(
            "foreign-record",
            member_user_ids=[bob.id],
            chat_type="record",
            res_model="lead",
            res_id=1,
        )

        resp = await client.get("/chats", params={"include_record": 1})
        assert resp.status_code == 200
        ids = {c["id"] for c in resp.json()["data"]}
        assert foreign_record not in ids

    async def test_admin_default_same_as_regular(self, client, user_factory):
        """
        is_admin alone grants NO extra visibility — admin must opt in
        via include_foreign.
        """
        admin_id = await self._login(
            client, user_factory, is_admin=True, login="admin_user"
        )
        bob = await user_factory(name="Bob", login="bob", is_admin=False)

        own = await self._mk_chat("own", member_user_ids=[admin_id])
        foreign = await self._mk_chat("foreign", member_user_ids=[bob.id])
        foreign_record = await self._mk_chat(
            "foreign-record",
            member_user_ids=[bob.id],
            chat_type="record",
            res_model="lead",
            res_id=1,
        )

        resp = await client.get("/chats")
        assert resp.status_code == 200
        ids = {c["id"] for c in resp.json()["data"]}
        assert own in ids
        assert foreign not in ids  # admin doesn't see foreign by default
        assert foreign_record not in ids

    async def test_admin_include_foreign_sees_all(self, client, user_factory):
        admin_id = await self._login(
            client, user_factory, is_admin=True, login="admin_user"
        )
        bob = await user_factory(name="Bob", login="bob", is_admin=False)

        own = await self._mk_chat("own", member_user_ids=[admin_id])
        foreign = await self._mk_chat("foreign", member_user_ids=[bob.id])

        resp = await client.get("/chats", params={"include_foreign": 1})
        assert resp.status_code == 200
        ids = {c["id"] for c in resp.json()["data"]}
        assert own in ids
        assert foreign in ids

    async def test_regular_include_foreign_forbidden(
        self, client, user_factory
    ):
        """Non-admin passing include_foreign=1 gets 403."""
        await self._login(client, user_factory, is_admin=False, login="alice")

        resp = await client.get("/chats", params={"include_foreign": 1})
        assert resp.status_code == 403

    async def test_admin_combo_flags(self, client, user_factory):
        """
        All three flags combine: admin sees foreign + deleted + record chats.
        """
        admin_id = await self._login(
            client, user_factory, is_admin=True, login="admin_user"
        )
        bob = await user_factory(name="Bob", login="bob", is_admin=False)

        foreign_deleted_record = await self._mk_chat(
            "foreign-deleted-record",
            member_user_ids=[bob.id],
            chat_type="record",
            active=False,
            res_model="lead",
            res_id=1,
        )

        # Without flags — hidden
        resp = await client.get("/chats")
        ids = {c["id"] for c in resp.json()["data"]}
        assert foreign_deleted_record not in ids

        # With all three — visible
        resp = await client.get(
            "/chats",
            params={
                "include_foreign": 1,
                "include_deleted": 1,
                "include_record": 1,
            },
        )
        assert resp.status_code == 200
        ids = {c["id"] for c in resp.json()["data"]}
        assert foreign_deleted_record in ids
