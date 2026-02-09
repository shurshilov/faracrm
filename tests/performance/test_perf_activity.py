"""
Performance: Activity (100 000 rows)

CRUD benchmarks on polymorphic activity table.
"""

import pytest

from tests.performance.conftest import perf_timer, chunked_create_bulk

pytestmark = [pytest.mark.performance, pytest.mark.asyncio]

MODULE = "Activity"


class TestActivityPerformance:

    # ── CREATE ──

    async def test_create_single(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity
        from backend.base.crm.activity.models.activity_type import ActivityType
        from datetime import date

        types = await ActivityType.search(fields=["id"], limit=1)
        type_id = types[0].id

        async with perf_timer(perf_report, MODULE, "create — single", 1):
            await Activity.create(
                Activity(
                    res_model="lead",
                    res_id=1,
                    activity_type_id=type_id,
                    user_id=1,
                    date_deadline=date.today(),
                    state="planned",
                    summary="Perf activity",
                )
            )

    async def test_create_bulk(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity
        from backend.base.crm.activity.models.activity_type import ActivityType
        from datetime import date

        types = await ActivityType.search(fields=["id"], limit=1)
        type_id = types[0].id

        n = 5_000
        payload = [
            Activity(
                res_model="lead",
                res_id=(i % 1000) + 1,
                activity_type_id=type_id,
                user_id=(i % 100) + 1,
                date_deadline=date.today(),
                state="planned",
                summary=f"Bulk activity {i}",
            )
            for i in range(n)
        ]

        async with perf_timer(perf_report, MODULE, f"create_bulk — {n:,}", n):
            await chunked_create_bulk(Activity, payload)

    # ── READ ──

    async def test_get_single(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        async with perf_timer(perf_report, MODULE, "get — single by id", 1):
            await Activity.get(1)

    async def test_search_by_user(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        async with perf_timer(
            perf_report, MODULE, "search — filter user_id", 100
        ):
            result = await Activity.search(
                fields=["id", "summary", "state", "date_deadline"],
                filter=[("user_id", "=", 1)],
                limit=200,
            )
        assert len(result) >= 1

    async def test_search_by_res_model(
        self, db_pool, seed_activities, perf_report
    ):
        """Filter by polymorphic field res_model."""
        from backend.base.crm.activity.models.activity import Activity

        async with perf_timer(
            perf_report, MODULE, "search — filter res_model='lead'", 1000
        ):
            result = await Activity.search(
                fields=["id", "summary", "state", "res_id"],
                filter=[("res_model", "=", "lead"), ("done", "=", False)],
                limit=1000,
            )
        assert len(result) >= 1

    async def test_search_overdue(self, db_pool, seed_activities, perf_report):
        """Find overdue activities (common dashboard query)."""
        from backend.base.crm.activity.models.activity import Activity

        async with perf_timer(
            perf_report, MODULE, "search — state='overdue'", 1000
        ):
            result = await Activity.search(
                fields=["id", "summary", "user_id", "date_deadline"],
                filter=[("state", "=", "overdue"), ("done", "=", False)],
                limit=1000,
            )

    async def test_search_count(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        async with perf_timer(
            perf_report, MODULE, "search_count — 100k table", 100_000
        ):
            count = await Activity.search_count()
        assert count >= 100_000

    # ── UPDATE ──

    async def test_update_single(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        act = await Activity.get(1)
        async with perf_timer(perf_report, MODULE, "update — single", 1):
            await act.update(Activity(state="done", done=True))

    async def test_update_bulk(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        n = 5_000
        ids = list(range(1, n + 1))

        async with perf_timer(perf_report, MODULE, f"update_bulk — {n:,}", n):
            await Activity.update_bulk(ids, Activity(notification_sent=True))

    # ── DELETE ──

    async def test_delete_single(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        act = await Activity.get(seed_activities)
        async with perf_timer(perf_report, MODULE, "delete — single", 1):
            await act.delete()

    async def test_delete_bulk(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        n = 2_000
        start = seed_activities - n
        ids = list(range(start, seed_activities))

        async with perf_timer(perf_report, MODULE, f"delete_bulk — {n:,}", n):
            await Activity.delete_bulk(ids)
