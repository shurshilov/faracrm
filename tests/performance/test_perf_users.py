"""
Performance: Users (10 000 rows)

CRUD benchmarks through ORM layer on 10k user dataset.
"""

import pytest
import pytest_asyncio

from tests.performance.conftest import perf_timer, chunked_create_bulk

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

        async with perf_timer(perf_report, MODULE, "create — single", 1):
            await User.create(
                User(
                    name="Perf User",
                    login="perf_single",
                    password_hash="h",
                    password_salt="s",
                    lang_id=lang_id,
                )
            )

    async def test_create_bulk(self, db_pool, seed_users, perf_report):
        """Bulk create 1 000 users via ORM create_bulk."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language

        langs = await Language.search(fields=["id"], limit=1)
        lang_id = langs[0].id

        n = 1_000
        payload = [
            User(
                name=f"Bulk User {i}",
                login=f"bulk_{i}",
                password_hash="h",
                password_salt="s",
                lang_id=lang_id,
            )
            for i in range(n)
        ]

        async with perf_timer(perf_report, MODULE, "create_bulk — 1 000", n):
            await chunked_create_bulk(User, payload)

    # ── READ ──

    async def test_get_single(self, db_pool, seed_users, perf_report):
        """Get one user by id."""
        from backend.base.crm.users.models.users import User

        async with perf_timer(perf_report, MODULE, "get — single by id", 1):
            await User.get(1)

    async def test_search_all(self, db_pool, seed_users, perf_report):
        """Search first 1 000 users (default page)."""
        from backend.base.crm.users.models.users import User

        n = 1_000
        async with perf_timer(perf_report, MODULE, f"search — limit {n}", n):
            result = await User.search(fields=["id", "name", "login"], limit=n)
        assert len(result) == n

    async def test_search_large_page(self, db_pool, seed_users, perf_report):
        """Search 10 000 users (full table scan)."""
        from backend.base.crm.users.models.users import User

        n = 10_000
        async with perf_timer(perf_report, MODULE, f"search — limit {n} (full)", n):
            result = await User.search(fields=["id", "name", "login"], limit=n)
        assert len(result) == n

    async def test_search_filter_login(self, db_pool, seed_users, perf_report):
        """Search with text filter: login ilike."""
        from backend.base.crm.users.models.users import User

        async with perf_timer(perf_report, MODULE, "search — filter login ilike", 1):
            result = await User.search(
                fields=["id", "name", "login"],
                filter=[("login", "ilike", "%user_500%")],
                limit=100,
            )
        assert len(result) >= 1

    async def test_search_filter_is_admin(self, db_pool, seed_users, perf_report):
        """Search with boolean filter."""
        from backend.base.crm.users.models.users import User

        async with perf_timer(
            perf_report, MODULE, "search — filter is_admin=false", 10_000
        ):
            result = await User.search(
                fields=["id", "name"],
                filter=[("is_admin", "=", False)],
                limit=10_000,
            )
        assert len(result) >= 1

    async def test_search_count(self, db_pool, seed_users, perf_report):
        """Count all users."""
        from backend.base.crm.users.models.users import User

        async with perf_timer(perf_report, MODULE, "search_count — all", 10_000):
            count = await User.search_count()
        assert count >= 10_000

    # ── UPDATE ──

    async def test_update_single(self, db_pool, seed_users, perf_report):
        """Update one user."""
        from backend.base.crm.users.models.users import User

        user = await User.get(1)
        async with perf_timer(perf_report, MODULE, "update — single", 1):
            await user.update(User(name="Updated Name"))

    async def test_update_bulk(self, db_pool, seed_users, perf_report):
        """Bulk update 5 000 users."""
        from backend.base.crm.users.models.users import User

        n = 5_000
        ids = list(range(1, n + 1))
        async with perf_timer(perf_report, MODULE, f"update_bulk — {n}", n):
            await User.update_bulk(ids, User(name="Bulk Updated"))

    # ── DELETE ──

    async def test_delete_single(self, db_pool, seed_users, perf_report):
        """Delete one user."""
        from backend.base.crm.users.models.users import User

        user = await User.get(seed_users)  # last user
        async with perf_timer(perf_report, MODULE, "delete — single", 1):
            await user.delete()

    async def test_delete_bulk(self, db_pool, seed_users, perf_report):
        """Bulk delete 1 000 users."""
        from backend.base.crm.users.models.users import User

        n = 1_000
        # take users from the end so we don't break FK refs
        start = seed_users - n
        ids = list(range(start, seed_users))

        async with perf_timer(perf_report, MODULE, f"delete_bulk — {n}", n):
            await User.delete_bulk(ids)
