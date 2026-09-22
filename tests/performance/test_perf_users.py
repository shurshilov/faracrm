"""
Performance: Users (10 000 rows)

CRUD benchmarks through ORM layer on 10k user dataset.

Каждая операция гоняется WARMUP + REPEAT (массовые — REPEAT_BULK) раз, см.
conftest.perf_run: уникальные логины и удаляемые id готовятся на все
прогоны итератором на RUNS / RUNS_BULK элементов.
"""

from itertools import count

import pytest

from tests.performance.conftest import REPEAT_BULK, RUNS, RUNS_BULK, perf_run

pytestmark = [pytest.mark.performance, pytest.mark.asyncio]

MODULE = "Users"


class TestUserPerformance:
    """CRUD perf tests on 10 000 users table."""

    # ── CREATE ──

    async def test_create_single(self, db_pool, seed_users, perf_report):
        """Create one user via ORM."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language

        langs = await Language.search(fields=["id"], limit=1)
        lang_id = langs[0].id
        # login уникален (@constrains) — свой на каждый прогон
        logins = (f"perf_single_{i}" for i in count())

        await perf_run(
            perf_report,
            MODULE,
            "create — single",
            1,
            lambda: User.create(
                User(
                    name="Perf User",
                    login=next(logins),
                    password_hash="h",
                    password_salt="s",
                    lang_id=lang_id,
                )
            ),
        )

    async def test_create_bulk(self, db_pool, seed_users, perf_report):
        """Bulk create 1 000 users via ORM create_bulk."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language

        langs = await Language.search(fields=["id"], limit=1)
        lang_id = langs[0].id

        n = 1_000
        batches = iter(
            [
                [
                    User(
                        name=f"Bulk User {i}",
                        login=f"bulk_{run}_{i}",
                        password_hash="h",
                        password_salt="s",
                        lang_id=lang_id,
                    )
                    for i in range(n)
                ]
                for run in range(RUNS_BULK)
            ]
        )

        await perf_run(
            perf_report,
            MODULE,
            "create_bulk — 1 000",
            n,
            lambda: User.create_bulk(next(batches)),
            repeat=REPEAT_BULK,
        )

    # ── READ ──

    async def test_get_single(self, db_pool, seed_users, perf_report):
        """Get one user by id."""
        from backend.base.crm.users.models.users import User

        await perf_run(
            perf_report, MODULE, "get — single by id", 1, lambda: User.get(1)
        )

    async def test_search_all(self, db_pool, seed_users, perf_report):
        """Search first 1 000 users (default page)."""
        from backend.base.crm.users.models.users import User

        n = 1_000

        async def run():
            result = await User.search(fields=["id", "name", "login"], limit=n)
            assert len(result) == n

        await perf_run(perf_report, MODULE, f"search — limit {n}", n, run)

    async def test_search_large_page(self, db_pool, seed_users, perf_report):
        """Search 10 000 users (full table scan)."""
        from backend.base.crm.users.models.users import User

        n = 10_000

        async def run():
            result = await User.search(fields=["id", "name", "login"], limit=n)
            assert len(result) == n

        await perf_run(
            perf_report, MODULE, f"search — limit {n} (full)", n, run
        )

    async def test_search_filter_login(self, db_pool, seed_users, perf_report):
        """Search with text filter: login ilike."""
        from backend.base.crm.users.models.users import User

        async def run():
            result = await User.search(
                fields=["id", "name", "login"],
                # ilike = подстрока: %…% добавляет парсер, "_" — литерал
                filter=[("login", "ilike", "user_500")],
                limit=100,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report, MODULE, "search — filter login ilike", 1, run
        )

    async def test_search_filter_is_admin(
        self, db_pool, seed_users, perf_report
    ):
        """Search with boolean filter."""
        from backend.base.crm.users.models.users import User

        async def run():
            result = await User.search(
                fields=["id", "name"],
                filter=[("is_admin", "=", False)],
                limit=10_000,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report, MODULE, "search — filter is_admin=false", 10_000, run
        )

    async def test_search_count(self, db_pool, seed_users, perf_report):
        """Count all users."""
        from backend.base.crm.users.models.users import User

        async def run():
            count_ = await User.search_count()
            assert count_ >= 10_000

        await perf_run(perf_report, MODULE, "search_count — all", 10_000, run)

    # ── UPDATE ──

    async def test_update_single(self, db_pool, seed_users, perf_report):
        """Update one user."""
        from backend.base.crm.users.models.users import User

        user = await User.get(1)
        await perf_run(
            perf_report,
            MODULE,
            "update — single",
            1,
            lambda: user.update(User(name="Updated Name")),
        )

    async def test_update_bulk(self, db_pool, seed_users, perf_report):
        """Bulk update 5 000 users."""
        from backend.base.crm.users.models.users import User

        n = 5_000
        ids = list(range(1, n + 1))
        await perf_run(
            perf_report,
            MODULE,
            f"update_bulk — {n}",
            n,
            lambda: User.update_bulk(ids, User(name="Bulk Updated")),
            repeat=REPEAT_BULK,
        )

    # ── DELETE ──

    async def test_delete_single(self, db_pool, seed_users, perf_report):
        """Delete one user — своя запись с конца таблицы на каждый прогон."""
        from backend.base.crm.users.models.users import User

        users = iter(
            [
                await User.get(seed_users - i, fields=["id"])
                for i in range(RUNS)
            ]
        )
        await perf_run(
            perf_report,
            MODULE,
            "delete — single",
            1,
            lambda: next(users).delete(),
        )

    async def test_delete_bulk(self, db_pool, seed_users, perf_report):
        """Bulk delete 1 000 users — своя пачка id на каждый прогон."""
        from backend.base.crm.users.models.users import User

        n = 1_000
        # take users from the end so we don't break FK refs; ниже одиночных
        top = seed_users - RUNS
        batches = iter(
            [
                list(range(top - n * (k + 1), top - n * k))
                for k in range(RUNS_BULK)
            ]
        )
        await perf_run(
            perf_report,
            MODULE,
            f"delete_bulk — {n}",
            n,
            lambda: User.delete_bulk(next(batches)),
            repeat=REPEAT_BULK,
        )
