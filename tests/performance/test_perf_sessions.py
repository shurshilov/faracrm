"""
Performance: Sessions (1 000 000 rows)

CRUD benchmarks on a million-row sessions table.
Typical high-load scenario: token lookup, session validation.

Каждая операция гоняется WARMUP + REPEAT (массовые — REPEAT_BULK) раз, см.
conftest.perf_run; токены и удаляемые записи готовятся на все прогоны.
"""

from datetime import datetime, timedelta, timezone
from itertools import count

import pytest

from tests.performance.conftest import REPEAT_BULK, RUNS, RUNS_BULK, perf_run

pytestmark = [pytest.mark.performance, pytest.mark.asyncio]

MODULE = "Sessions"


class TestSessionPerformance:
    """CRUD perf tests on 1M sessions table."""

    # ── CREATE ──

    async def test_create_single(self, db_pool, seed_sessions, perf_report):
        """Create one session via ORM."""
        from backend.base.crm.security.models.sessions import Session

        expired = datetime.now(timezone.utc) + timedelta(days=1)
        tokens = (f"perf_token_single_{i}" for i in count())

        await perf_run(
            perf_report,
            MODULE,
            "create — single",
            1,
            lambda: Session.create(
                Session(
                    user_id=1,
                    token=next(tokens),
                    ttl=86400,
                    expired_datetime=expired,
                    create_user_id=1,
                    update_user_id=1,
                    active=True,
                )
            ),
        )

    async def test_create_bulk(self, db_pool, seed_sessions, perf_report):
        """Bulk create 10 000 sessions."""
        from backend.base.crm.security.models.sessions import Session

        n = 10_000
        now = datetime.now(timezone.utc)
        batches = iter(
            [
                [
                    Session(
                        user_id=(i % 10_000) + 1,
                        token=f"bulk_token_{run}_{i}",
                        ttl=86400,
                        expired_datetime=now + timedelta(days=1),
                        create_user_id=1,
                        update_user_id=1,
                        active=True,
                    )
                    for i in range(n)
                ]
                for run in range(RUNS_BULK)
            ]
        )

        await perf_run(
            perf_report,
            MODULE,
            f"create_bulk — {n:,}",
            n,
            lambda: Session.create_bulk(next(batches)),
            repeat=REPEAT_BULK,
        )

    # ── READ ──

    async def test_get_single(self, db_pool, seed_sessions, perf_report):
        """Get session by id from 1M table."""
        from backend.base.crm.security.models.sessions import Session

        await perf_run(
            perf_report,
            MODULE,
            "get — single by id",
            1,
            lambda: Session.get(1),
        )

    async def test_search_by_user(
        self, db_pool, seed_sessions, seed_users, perf_report
    ):
        """Search sessions for a specific user (~100 results in 1M)."""
        from backend.base.crm.security.models.sessions import Session

        async def run():
            result = await Session.search(
                fields=["id", "token", "active"],
                filter=[("user_id", "=", 1)],
                limit=200,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report,
            MODULE,
            "search — filter user_id (indexed FK)",
            100,
            run,
        )

    async def test_search_active(self, db_pool, seed_sessions, perf_report):
        """Search active sessions — boolean filter on 1M rows."""
        from backend.base.crm.security.models.sessions import Session

        n = 1_000

        async def run():
            result = await Session.search(
                fields=["id", "token", "user_id"],
                filter=[("active", "=", True)],
                limit=n,
            )
            assert len(result) == n

        await perf_run(
            perf_report,
            MODULE,
            f"search — filter active=true, limit {n}",
            n,
            run,
        )

    async def test_search_token_exact(
        self, db_pool, seed_sessions, perf_report
    ):
        """Lookup session by token (indexed char field) — hot path."""
        from backend.base.crm.security.models.sessions import Session

        # Get a real token first
        session = await Session.get(1)
        token = session.token

        async def run():
            result = await Session.search(
                fields=["id", "user_id", "active"],
                filter=[("token", "=", token)],
                limit=1,
            )
            assert len(result) == 1

        await perf_run(
            perf_report,
            MODULE,
            "search — filter token=exact (indexed)",
            1,
            run,
        )

    async def test_session_check_raw_sql(
        self, db_pool, seed_sessions, perf_report
    ):
        """session_check (raw SQL JOIN) — the real auth hot path."""
        from backend.base.crm.security.models.sessions import Session

        sess = await Session.get(1)
        token = sess.token

        async def run():
            try:
                await Session.session_check(token)
            except Exception:
                pass  # may fail if expired, we care about timing

        await perf_run(
            perf_report, MODULE, "session_check — raw SQL auth path", 1, run
        )

    async def test_search_count(self, db_pool, seed_sessions, perf_report):
        """Count all sessions in 1M table."""
        from backend.base.crm.security.models.sessions import Session

        async def run():
            count_ = await Session.search_count()
            assert count_ >= 1_000_000

        await perf_run(
            perf_report, MODULE, "search_count — 1M table", 1_000_000, run
        )

    # ── UPDATE ──

    async def test_update_single(self, db_pool, seed_sessions, perf_report):
        """Update one session."""
        from backend.base.crm.security.models.sessions import Session

        session = await Session.get(1)
        await perf_run(
            perf_report,
            MODULE,
            "update — single",
            1,
            lambda: session.update(Session(active=False)),
        )

    async def test_update_bulk(self, db_pool, seed_sessions, perf_report):
        """Bulk update 10 000 sessions (deactivate)."""
        from backend.base.crm.security.models.sessions import Session

        n = 10_000
        ids = list(range(1, n + 1))

        await perf_run(
            perf_report,
            MODULE,
            f"update_bulk — {n:,}",
            n,
            lambda: Session.update_bulk(ids, Session(active=False)),
            repeat=REPEAT_BULK,
        )

    # ── DELETE ──

    async def test_delete_single(self, db_pool, seed_sessions, perf_report):
        """Delete one session from 1M table — своя запись на каждый прогон."""
        from backend.base.crm.security.models.sessions import Session

        sessions = iter(
            [
                await Session.get(seed_sessions - i, fields=["id"])
                for i in range(RUNS)
            ]
        )
        await perf_run(
            perf_report,
            MODULE,
            "delete — single",
            1,
            lambda: next(sessions).delete(),
        )

    async def test_delete_bulk(self, db_pool, seed_sessions, perf_report):
        """Bulk delete 5 000 sessions — своя пачка id на каждый прогон."""
        from backend.base.crm.security.models.sessions import Session

        n = 5_000
        top = seed_sessions - RUNS
        batches = iter(
            [
                list(range(top - n * (k + 1), top - n * k))
                for k in range(RUNS_BULK)
            ]
        )

        await perf_run(
            perf_report,
            MODULE,
            f"delete_bulk — {n:,}",
            n,
            lambda: Session.delete_bulk(next(batches)),
            repeat=REPEAT_BULK,
        )
