"""
Performance: Chat / Messages / Members (1 000 000 messages, 5 000 members)

Covers:
- Message CRUD on 1M-row table
- Member queries on large chat (5k subscribers)
- Chat listing with filters
- get_chat_messages pagination (the real hot path)

Каждая операция гоняется WARMUP + REPEAT (массовые — REPEAT_BULK) раз, см.
conftest.perf_run; удаляемые сообщения готовятся на все прогоны.
"""

import pytest

from tests.performance.conftest import REPEAT_BULK, RUNS, RUNS_BULK, perf_run

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

        info = seed_chat_and_messages

        await perf_run(
            perf_report,
            MODULE,
            "message create — single",
            1,
            lambda: ChatMessage.create(
                ChatMessage(
                    chat_id=info["big_chat_id"],
                    body="Perf test message",
                    message_type="comment",
                    author_user_id=1,
                )
            ),
        )

    async def test_create_bulk_messages(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Bulk create 5 000 messages."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        info = seed_chat_and_messages
        n = 5_000
        batches = iter(
            [
                [
                    ChatMessage(
                        chat_id=info["big_chat_id"],
                        body=f"Bulk msg {i}",
                        message_type="comment",
                        author_user_id=(i % 100) + 1,
                    )
                    for i in range(n)
                ]
                for _ in range(RUNS_BULK)
            ]
        )

        await perf_run(
            perf_report,
            MODULE,
            f"message create_bulk — {n:,}",
            n,
            lambda: ChatMessage.create_bulk(next(batches)),
            repeat=REPEAT_BULK,
        )

    # ── READ ──

    async def test_get_single_message(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Get one message by id from 1M table."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        await perf_run(
            perf_report,
            MODULE,
            "message get — single by id",
            1,
            lambda: ChatMessage.get(1),
        )

    async def test_search_messages_by_chat(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Search messages for a specific chat (ORM filter)."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        info = seed_chat_and_messages
        n = 50

        async def run():
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

        await perf_run(
            perf_report,
            MODULE,
            f"message search — chat_id filter, limit {n}",
            n,
            run,
        )

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

        async def run():
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

        await perf_run(
            perf_report,
            MODULE,
            "message search — before_id pagination",
            n,
            run,
        )

    async def test_search_unread_messages(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Search unread messages in a chat.

        Флага is_read у сообщения нет: непрочитанное = id больше watermark
        участника (chat_member.last_read_message_id). Сид watermark не
        ставит, эмулируем «прочитано всё, кроме последних 5 000».
        """
        from backend.base.crm.chat.models.chat_message import ChatMessage

        info = seed_chat_and_messages
        last = await ChatMessage.search_one(
            fields=["id"],
            filter=[("chat_id", "=", info["big_chat_id"])],
            sort="id",
            order="DESC",
        )
        watermark = (last.id if last else 0) - 5_000

        async def run():
            result = await ChatMessage.search(
                fields=["id"],
                filter=[
                    ("chat_id", "=", info["big_chat_id"]),
                    ("is_deleted", "=", False),
                    ("id", ">", watermark),
                ],
                limit=1000,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report,
            MODULE,
            "message search — unread (id > watermark)",
            1000,
            run,
        )

    async def test_search_starred_messages(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Search starred messages across all chats (~5% of 1M)."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        await perf_run(
            perf_report,
            MODULE,
            "message search — starred=true, limit 100",
            100,
            lambda: ChatMessage.search(
                fields=["id", "body", "chat_id", "create_date"],
                filter=[("starred", "=", True), ("is_deleted", "=", False)],
                limit=100,
            ),
        )

    async def test_search_count_messages(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Count all messages in 1M table."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        async def run():
            count = await ChatMessage.search_count()
            assert count >= 1_000_000

        await perf_run(
            perf_report,
            MODULE,
            "message search_count — 1M table",
            1_000_000,
            run,
        )

    async def test_search_count_by_chat(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Count messages in one chat."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        info = seed_chat_and_messages

        async def run():
            count = await ChatMessage.search_count(
                filter=[
                    ("chat_id", "=", info["big_chat_id"]),
                    ("is_deleted", "=", False),
                ]
            )
            assert count >= 1

        await perf_run(
            perf_report,
            MODULE,
            "message search_count — single chat",
            10_000,
            run,
        )

    # ── UPDATE ──

    async def test_update_single_message(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Update one message (edit body)."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        msg = await ChatMessage.get(1)
        await perf_run(
            perf_report,
            MODULE,
            "message update — single",
            1,
            lambda: msg.update(
                ChatMessage(body="Edited body", is_edited=True)
            ),
        )

    async def test_update_bulk_starred(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Bulk update: star 10 000 messages (mark-read теперь одна строка
        watermark в chat_member, массовый апдейт сообщений — starred)."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        n = 10_000
        ids = list(range(1, n + 1))

        await perf_run(
            perf_report,
            MODULE,
            f"message update_bulk — starred {n:,}",
            n,
            lambda: ChatMessage.update_bulk(ids, ChatMessage(starred=True)),
            repeat=REPEAT_BULK,
        )

    # ── DELETE ──

    async def test_delete_single_message(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Delete one message — своя запись с конца таблицы на каждый прогон."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        info = seed_chat_and_messages
        msgs = iter(
            [
                await ChatMessage.get(info["messages"] - i, fields=["id"])
                for i in range(RUNS)
            ]
        )
        await perf_run(
            perf_report,
            MODULE,
            "message delete — single",
            1,
            lambda: next(msgs).delete(),
        )

    async def test_delete_bulk_messages(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Bulk delete 100 messages — своя пачка id на каждый прогон."""
        from backend.base.crm.chat.models.chat_message import ChatMessage

        info = seed_chat_and_messages
        n = 100
        top = info["messages"] - RUNS
        batches = iter(
            [
                list(range(top - n * (k + 1), top - n * k))
                for k in range(RUNS_BULK)
            ]
        )

        await perf_run(
            perf_report,
            MODULE,
            f"message delete_bulk — {n:,}",
            n,
            lambda: ChatMessage.delete_bulk(next(batches)),
            repeat=REPEAT_BULK,
        )


class TestChatMemberPerformance:
    """Queries on chat with 5 000 subscribers."""

    async def test_search_members_big_chat(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """List all members of big chat (5 000 subscribers)."""
        from backend.base.crm.chat.models.chat_member import ChatMember

        info = seed_chat_and_messages
        n = 5_000

        async def run():
            result = await ChatMember.search(
                fields=["id", "user_id", "is_active", "is_admin", "can_write"],
                filter=[
                    ("chat_id", "=", info["big_chat_id"]),
                    ("is_active", "=", True),
                ],
                limit=n,
            )
            assert len(result) >= 1000

        await perf_run(
            perf_report, MODULE, f"members search — big chat ({n:,})", n, run
        )

    async def test_check_membership(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Check single user membership (the auth hot path)."""
        from backend.base.crm.chat.models.chat_member import ChatMember

        info = seed_chat_and_messages

        async def run():
            member = await ChatMember.get_membership(info["big_chat_id"], 1)
            assert member is not None

        await perf_run(
            perf_report, MODULE, "members check_membership — single", 1, run
        )

    async def test_search_user_chats(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """List all chats for a user (across all memberships)."""
        from backend.base.crm.chat.models.chat_member import ChatMember

        async def run():
            result = await ChatMember.search(
                fields=["id", "chat_id", "is_active"],
                filter=[("user_id", "=", 1), ("is_active", "=", True)],
                limit=200,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report,
            MODULE,
            "members search — all chats for user",
            100,
            run,
        )


class TestChatPerformance:
    """Chat table CRUD (100 chats)."""

    async def test_search_chats(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """List all active chats."""
        from backend.base.crm.chat.models.chat import Chat

        async def run():
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

        await perf_run(
            perf_report, MODULE, "chat search — all active", 100, run
        )

    async def test_search_chats_by_type(
        self, db_pool, seed_chat_and_messages, perf_report
    ):
        """Filter chats by type."""
        from backend.base.crm.chat.models.chat import Chat

        async def run():
            result = await Chat.search(
                fields=["id", "name", "chat_type"],
                filter=[("chat_type", "=", "channel"), ("active", "=", True)],
                limit=100,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report, MODULE, "chat search — filter type=channel", 10, run
        )
