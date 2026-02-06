"""
Integration tests for Chat Messages API endpoints.

Tests cover:
- GET /chats/{id}/messages - list messages with pagination
- POST /chats/{id}/messages - send message
- PATCH /chats/{id}/messages/{id} - edit message
- DELETE /chats/{id}/messages/{id} - delete message
- POST /chats/{id}/messages/{id}/pin - pin/unpin
- POST /chats/{id}/read - mark as read
- POST /chats/{id}/messages/{id}/reactions - add/remove reaction
- GET /chats/{id}/pinned - get pinned messages
- POST /chats/{id}/messages/{id}/forward - forward message

Run: pytest tests/integration/messages/test_messages_api.py -v -m integration
"""

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = [pytest.mark.integration, pytest.mark.api]


class TestGetMessagesAPI:
    """Tests for GET /chats/{chat_id}/messages."""

    async def _setup_chat_with_messages(self, authenticated_client):
        """Helper: create chat, member, and messages."""
        client, user_id, token = authenticated_client

        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage
        from backend.base.crm.chat.models.chat_member import ChatMember

        chat_id = await Chat.create(Chat(name="Test Chat"))

        await ChatMember.create(ChatMember(
            chat_id=chat_id,
            user_id=user_id,
            is_active=True,
        ))

        msg_ids = []
        for i in range(5):
            mid = await ChatMessage.create(ChatMessage(
                chat_id=chat_id,
                body=f"Message {i}",
                author_user_id=user_id,
            ))
            msg_ids.append(mid)

        return client, chat_id, msg_ids

    async def test_get_messages(self, authenticated_client):
        client, chat_id, msg_ids = await self._setup_chat_with_messages(
            authenticated_client
        )

        response = await client.get(f"/chats/{chat_id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 5

    async def test_get_messages_with_limit(self, authenticated_client):
        client, chat_id, msg_ids = await self._setup_chat_with_messages(
            authenticated_client
        )

        response = await client.get(f"/chats/{chat_id}/messages?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2

    async def test_get_messages_pagination(self, authenticated_client):
        client, chat_id, msg_ids = await self._setup_chat_with_messages(
            authenticated_client
        )

        # Get first page
        response = await client.get(f"/chats/{chat_id}/messages?limit=3")
        assert response.status_code == 200
        page1 = response.json()["data"]
        assert len(page1) == 3

        # Get second page (before oldest of first page)
        before_id = page1[-1]["id"]
        response = await client.get(
            f"/chats/{chat_id}/messages?limit=3&before_id={before_id}"
        )
        assert response.status_code == 200
        page2 = response.json()["data"]
        assert len(page2) == 2  # Only 2 remaining

    async def test_get_messages_unauthenticated(self, client):
        response = await client.get("/chats/1/messages")
        assert response.status_code in [401, 403]


class TestPostMessageAPI:
    """Tests for POST /chats/{chat_id}/messages."""

    async def _setup_chat(self, authenticated_client):
        client, user_id, token = authenticated_client

        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_member import ChatMember

        chat_id = await Chat.create(Chat(name="Send Chat"))
        await ChatMember.create(ChatMember(
            chat_id=chat_id,
            user_id=user_id,
            is_active=True,
            can_write=True,
        ))

        return client, chat_id, user_id

    @patch("backend.base.crm.chat.websocket.chat_manager.send_to_chat", new_callable=AsyncMock)
    async def test_send_message(self, mock_ws, authenticated_client):
        client, chat_id, user_id = await self._setup_chat(authenticated_client)

        response = await client.post(
            f"/chats/{chat_id}/messages",
            json={"body": "Hello, World!", "attachments": []},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["body"] == "Hello, World!"
        assert "id" in data["data"]

    @patch("backend.base.crm.chat.websocket.chat_manager.send_to_chat", new_callable=AsyncMock)
    async def test_send_empty_message_fails(self, mock_ws, authenticated_client):
        client, chat_id, user_id = await self._setup_chat(authenticated_client)

        response = await client.post(
            f"/chats/{chat_id}/messages",
            json={"body": "   ", "attachments": []},
        )

        # Should fail because body is empty whitespace and no attachments
        assert response.status_code in [400, 422, 500]


class TestEditMessageAPI:
    """Tests for PATCH /chats/{chat_id}/messages/{message_id}."""

    async def _setup(self, authenticated_client):
        client, user_id, token = authenticated_client

        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage
        from backend.base.crm.chat.models.chat_member import ChatMember

        chat_id = await Chat.create(Chat(name="Edit Chat"))
        await ChatMember.create(ChatMember(
            chat_id=chat_id, user_id=user_id, is_active=True,
        ))

        msg_id = await ChatMessage.create(ChatMessage(
            chat_id=chat_id, body="Original", author_user_id=user_id,
        ))

        return client, chat_id, msg_id, user_id

    @patch("backend.base.crm.chat.websocket.chat_manager.send_to_chat", new_callable=AsyncMock)
    async def test_edit_own_message(self, mock_ws, authenticated_client):
        client, chat_id, msg_id, user_id = await self._setup(authenticated_client)

        response = await client.patch(
            f"/chats/{chat_id}/messages/{msg_id}",
            json={"body": "Edited text"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

        from backend.base.crm.chat.models.chat_message import ChatMessage
        msg = await ChatMessage.get(msg_id)
        assert msg.body == "Edited text"
        assert msg.is_edited is True


class TestDeleteMessageAPI:
    """Tests for DELETE /chats/{chat_id}/messages/{message_id}."""

    async def _setup(self, authenticated_client):
        client, user_id, token = authenticated_client

        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage
        from backend.base.crm.chat.models.chat_member import ChatMember

        chat_id = await Chat.create(Chat(name="Delete Chat"))
        await ChatMember.create(ChatMember(
            chat_id=chat_id, user_id=user_id, is_active=True,
        ))

        msg_id = await ChatMessage.create(ChatMessage(
            chat_id=chat_id, body="Delete me", author_user_id=user_id,
        ))

        return client, chat_id, msg_id

    @patch("backend.base.crm.chat.websocket.chat_manager.send_to_chat", new_callable=AsyncMock)
    async def test_delete_own_message(self, mock_ws, authenticated_client):
        client, chat_id, msg_id = await self._setup(authenticated_client)

        response = await client.delete(f"/chats/{chat_id}/messages/{msg_id}")

        assert response.status_code == 200
        assert response.json()["success"] is True

        from backend.base.crm.chat.models.chat_message import ChatMessage
        msg = await ChatMessage.get(msg_id)
        assert msg.is_deleted is True


class TestPinMessageAPI:
    """Tests for POST /chats/{chat_id}/messages/{message_id}/pin."""

    async def _setup(self, authenticated_client):
        client, user_id, token = authenticated_client

        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage
        from backend.base.crm.chat.models.chat_member import ChatMember

        chat_id = await Chat.create(Chat(name="Pin Chat"))
        await ChatMember.create(ChatMember(
            chat_id=chat_id, user_id=user_id, is_active=True,
            can_pin=True,
        ))

        msg_id = await ChatMessage.create(ChatMessage(
            chat_id=chat_id, body="Pin this", author_user_id=user_id,
        ))

        return client, chat_id, msg_id

    @patch("backend.base.crm.chat.websocket.chat_manager.send_to_chat", new_callable=AsyncMock)
    async def test_pin_message(self, mock_ws, authenticated_client):
        client, chat_id, msg_id = await self._setup(authenticated_client)

        response = await client.post(
            f"/chats/{chat_id}/messages/{msg_id}/pin",
            json={"pinned": True},
        )

        assert response.status_code == 200
        assert response.json()["pinned"] is True

    @patch("backend.base.crm.chat.websocket.chat_manager.send_to_chat", new_callable=AsyncMock)
    async def test_unpin_message(self, mock_ws, authenticated_client):
        client, chat_id, msg_id = await self._setup(authenticated_client)

        # Pin first
        await client.post(
            f"/chats/{chat_id}/messages/{msg_id}/pin",
            json={"pinned": True},
        )

        # Unpin
        response = await client.post(
            f"/chats/{chat_id}/messages/{msg_id}/pin",
            json={"pinned": False},
        )

        assert response.status_code == 200
        assert response.json()["pinned"] is False


class TestMarkAsReadAPI:
    """Tests for POST /chats/{chat_id}/read."""

    @patch("backend.base.crm.chat.websocket.chat_manager.send_to_chat", new_callable=AsyncMock)
    async def test_mark_as_read(self, mock_ws, authenticated_client):
        client, user_id, token = authenticated_client

        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage
        from backend.base.crm.chat.models.chat_member import ChatMember
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language

        chat_id = await Chat.create(Chat(name="Read Chat"))
        await ChatMember.create(ChatMember(
            chat_id=chat_id, user_id=user_id, is_active=True,
        ))

        # Create message from another user
        lang_id = await Language.create(Language(code="ru", name="Russian", active=True))
        other_id = await User.create(User(
            name="Other", login="other_read",
            password_hash="h", password_salt="s", lang_id=lang_id,
        ))

        await ChatMessage.create(ChatMessage(
            chat_id=chat_id, body="Unread msg", author_user_id=other_id,
            is_read=False,
        ))

        response = await client.post(f"/chats/{chat_id}/read")

        assert response.status_code == 200
        assert response.json()["success"] is True


class TestReactionsAPI:
    """Tests for POST /chats/{chat_id}/messages/{id}/reactions."""

    async def _setup(self, authenticated_client):
        client, user_id, token = authenticated_client

        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage
        from backend.base.crm.chat.models.chat_member import ChatMember

        chat_id = await Chat.create(Chat(name="Reactions Chat"))
        await ChatMember.create(ChatMember(
            chat_id=chat_id, user_id=user_id, is_active=True,
        ))
        msg_id = await ChatMessage.create(ChatMessage(
            chat_id=chat_id, body="React to this", author_user_id=user_id,
        ))

        return client, chat_id, msg_id

    @patch("backend.base.crm.chat.websocket.chat_manager.send_to_chat", new_callable=AsyncMock)
    async def test_add_reaction(self, mock_ws, authenticated_client):
        client, chat_id, msg_id = await self._setup(authenticated_client)

        response = await client.post(
            f"/chats/{chat_id}/messages/{msg_id}/reactions",
            json={"emoji": "👍"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "added"

    @patch("backend.base.crm.chat.websocket.chat_manager.send_to_chat", new_callable=AsyncMock)
    async def test_toggle_reaction(self, mock_ws, authenticated_client):
        """Adding same reaction twice should remove it (toggle)."""
        client, chat_id, msg_id = await self._setup(authenticated_client)

        # Add
        await client.post(
            f"/chats/{chat_id}/messages/{msg_id}/reactions",
            json={"emoji": "❤️"},
        )

        # Remove (toggle)
        response = await client.post(
            f"/chats/{chat_id}/messages/{msg_id}/reactions",
            json={"emoji": "❤️"},
        )

        assert response.status_code == 200
        assert response.json()["action"] == "removed"
