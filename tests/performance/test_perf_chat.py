"""
Performance: Chat / Messages / Members (1 000 000 messages, 5 000 members)

Covers:
- Message CRUD on 1M-row table
- Member queries on large chat (5k subscribers)
- Chat listing with filters
- get_chat_messages pagination (the real hot path)
"""

import pytest

from tests.performance.conftest import perf_timer, chunked_create_bulk

pytestmark = [pytest.mark.performance, pytest.mark.asyncio]

MODULE = "Chat"


class TestChatMessagePerformance:
    """Message CRUD on 1M messages table."""

    # ── CREATE ──

    async def test_create_single_message(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Create one message via ORM."""
        from backend.base.crm.chat.models.chat_message import ChatMessage
        from datetime import datetime, timezone

        info = seed_chat_and_messages
        now = datetime.now(timezone.utc)

        async with perf_timer(
            perf_report, MODULE, "message create — single", 1
        ):
            await ChatMessage.create(
                ChatMessage(
                    chat_id=info["big_chat_id"],
                    body="Perf test message",
                    message_type="comment",
                    author_user_id=1,
                    create_date=now,
                    write_date=now,
                )
            )

    async def test_create_bulk_messages(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Bulk create 5 000 messages."""
        from backend.base.crm.chat.models.chat_message import ChatMessage
        from datetime import datetime, timezone

        info = seed_chat_and_messages
        now = datetime.now(timezone.utc)
        n = 5_000
        payload = [
            ChatMessage(
                chat_id=info["big_chat_id"],
                body=f"Bulk msg {i}",
                message_type="comment",
                author_user_id=(i % 100) + 1,
                create_date=now,
                write_date=now,
            )
            for i in range(n)
        ]

        async with perf_timer(
            perf_report, MODULE, f"message create_bulk — {n:,}", n
        ):
            await chunked_create_bulk(ChatMessage, payload)

    # ── READ ──

    async def test_get_single_message(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Get one message by id from 1M table."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        async with perf_timer(
            perf_report, MODULE, "message get — single by id", 1
        ):
            await ChatMessage.get(1)

    async def test_search_messages_by_chat(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Search messages for a specific chat (ORM filter)."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        info = seed_chat_and_messages
        n = 50

        async with perf_timer(
            perf_report,
            MODULE,
            f"message search — chat_id filter, limit {n}",
            n,
        ):
            result = await ChatMessage.search(
                fields=["id", "body", "author_user_id", "create_date"],
                filter=[
                    ("chat_id", "=", info["big_chat_id"]),
                    ("is_deleted", "=", False),
                ],
                sort="id",
                order="DESC",
                limit=n,
            )
        assert len(result) >= 1

    async def test_search_messages_pagination(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Paginated search: before_id pattern (infinite scroll)."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        info = seed_chat_and_messages

        # Get last message id for the big chat
        latest = await ChatMessage.search(
            fields=["id"],
            filter=[("chat_id", "=", info["big_chat_id"])],
            sort="id",
            order="DESC",
            limit=1,
        )
        before_id = latest[0].id if latest else 999999999

        n = 50
        async with perf_timer(
            perf_report, MODULE, f"message search — before_id pagination", n
        ):
            result = await ChatMessage.search(
                fields=[
                    "id",
                    "body",
                    "message_type",
                    "author_user_id",
                    "create_date",
                    "starred",
                    "pinned",
                    "is_edited",
                    "is_read",
                ],
                filter=[
                    ("chat_id", "=", info["big_chat_id"]),
                    ("is_deleted", "=", False),
                    ("id", "<", before_id),
                ],
                sort="id",
                order="DESC",
                limit=n,
            )
        assert len(result) >= 1

    async def test_search_unread_messages(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Search unread messages in a chat."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        info = seed_chat_and_messages

        async with perf_timer(
            perf_report, MODULE, "message search — unread in chat", 1000
        ):
            result = await ChatMessage.search(
                fields=["id"],
                filter=[
                    ("chat_id", "=", info["big_chat_id"]),
                    ("is_read", "=", False),
                    ("is_deleted", "=", False),
                ],
                limit=1000,
            )

    async def test_search_starred_messages(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Search starred messages across all chats (~5% of 1M)."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        async with perf_timer(
            perf_report,
            MODULE,
            "message search — starred=true, limit 100",
            100,
        ):
            result = await ChatMessage.search(
                fields=["id", "body", "chat_id", "create_date"],
                filter=[("starred", "=", True), ("is_deleted", "=", False)],
                limit=100,
            )

    async def test_search_count_messages(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Count all messages in 1M table."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        async with perf_timer(
            perf_report, MODULE, "message search_count — 1M table", 1_000_000
        ):
            count = await ChatMessage.search_count()
        assert count >= 1_000_000

    async def test_search_count_by_chat(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Count messages in one chat."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        info = seed_chat_and_messages

        async with perf_timer(
            perf_report, MODULE, "message search_count — single chat", 10_000
        ):
            count = await ChatMessage.search_count(
                filter=[
                    ("chat_id", "=", info["big_chat_id"]),
                    ("is_deleted", "=", False),
                ]
            )
        assert count >= 1

    # ── UPDATE ──

    async def test_update_single_message(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Update one message (edit body)."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        msg = await ChatMessage.get(1)
        async with perf_timer(
            perf_report, MODULE, "message update — single", 1
        ):
            await msg.update(ChatMessage(body="Edited body", is_edited=True))

    async def test_update_bulk_mark_read(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Bulk update: mark 10 000 messages as read."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        n = 10_000
        ids = list(range(1, n + 1))

        async with perf_timer(
            perf_report, MODULE, f"message update_bulk — mark_read {n:,}", n
        ):
            await ChatMessage.update_bulk(ids, ChatMessage(is_read=True))

    # ── DELETE ──

    async def test_delete_single_message(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Delete one message."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        msg = await ChatMessage.get(3)
        async with perf_timer(
            perf_report, MODULE, "message delete — single", 1
        ):
            await msg.delete()

    async def test_delete_bulk_messages(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Bulk delete 5 000 messages."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        n = 1_00
        ids = list(range(100, 100 + n))

        async with perf_timer(
            perf_report, MODULE, f"message delete_bulk — {n:,}", n
        ):
            await ChatMessage.delete_bulk(ids)


class TestChatMemberPerformance:
    """Queries on chat with 5 000 subscribers."""

    async def test_search_members_big_chat(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """List all members of big chat (5 000 subscribers)."""
        from backend.base.crm.chat.models.chat_member import ChatMember

        info = seed_chat_and_messages
        n = 5_000

        async with perf_timer(
            perf_report, MODULE, f"members search — big chat ({n:,})", n
        ):
            result = await ChatMember.search(
                fields=["id", "user_id", "is_active", "is_admin", "can_write"],
                filter=[
                    ("chat_id", "=", info["big_chat_id"]),
                    ("is_active", "=", True),
                ],
                limit=n,
            )
        assert len(result) >= 1000

    async def test_check_membership(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Check single user membership (the auth hot path)."""
        from backend.base.crm.chat.models.chat_member import ChatMember

        info = seed_chat_and_messages

        async with perf_timer(
            perf_report, MODULE, "members check_membership — single", 1
        ):
            member = await ChatMember.get_membership(info["big_chat_id"], 1)
        assert member is not None

    async def test_search_user_chats(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """List all chats for a user (across all memberships)."""
        from backend.base.crm.chat.models.chat_member import ChatMember

        async with perf_timer(
            perf_report, MODULE, "members search — all chats for user", 100
        ):
            result = await ChatMember.search(
                fields=["id", "chat_id", "is_active"],
                filter=[("user_id", "=", 1), ("is_active", "=", True)],
                limit=200,
            )
        assert len(result) >= 1


class TestChatPerformance:
    """Chat table CRUD (100 chats)."""

    async def test_search_chats(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """List all active chats."""
        from backend.base.crm.chat.models.chat import Chat

        async with perf_timer(
            perf_report, MODULE, "chat search — all active", 100
        ):
            result = await Chat.search(
                fields=[
                    "id",
                    "name",
                    "chat_type",
                    "active",
                    "last_message_date",
                ],
                filter=[("active", "=", True)],
                limit=200,
            )
        assert len(result) >= 1

    async def test_search_chats_by_type(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Filter chats by type."""
        from backend.base.crm.chat.models.chat import Chat

        async with perf_timer(
            perf_report, MODULE, "chat search — filter type=channel", 10
        ):
            result = await Chat.search(
                fields=["id", "name", "chat_type"],
                filter=[("chat_type", "=", "channel"), ("active", "=", True)],
                limit=100,
            )
        assert len(result) >= 1
