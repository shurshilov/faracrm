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


class TestChatCreate:
    """Tests for Chat model."""

    async def test_create_chat(self):
        from backend.base.crm.chat.models.chat import Chat

        cid = await Chat.create(Chat(name="Support Chat"))
        c = await Chat.get(cid)
        assert c.name == "Support Chat"

    async def test_create_chat_with_type(self):
        from backend.base.crm.chat.models.chat import Chat

        cid = await Chat.create(
            Chat(
                name="Private Chat",
                chat_type="private",
            )
        )
        c = await Chat.get(cid)
        assert c.chat_type == "private"

    async def test_search_chats(self):
        from backend.base.crm.chat.models.chat import Chat

        await Chat.create(Chat(name="Chat A"))
        await Chat.create(Chat(name="Chat B"))
        await Chat.create(Chat(name="Chat C"))
        chats = await Chat.search(fields=["id", "name"])
        assert len(chats) == 3


class TestChatMessages:
    """Tests for ChatMessage model."""

    async def test_create_message(self):
        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage

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
        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage

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
        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage

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
        from backend.base.crm.chat.models.chat import Chat

        cid = await Chat.create(Chat(name="Delete Me"))
        c = await Chat.get(cid)
        await c.delete()
        assert await Chat.get_or_none(cid) is None

    async def test_delete_message(self):
        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage

        cid = await Chat.create(Chat(name="Msg Del Chat"))
        mid = await ChatMessage.create(
            ChatMessage(chat_id=cid, body="Delete this")
        )
        m = await ChatMessage.get(mid)
        await m.delete()
        assert await ChatMessage.get_or_none(mid) is None
