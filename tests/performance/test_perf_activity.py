"""
Performance: Activity (100 000 rows)

CRUD benchmarks on polymorphic activity table.

Каждая операция гоняется WARMUP + REPEAT (массовые — REPEAT_BULK) раз, см.
conftest.perf_run; удаляемые записи готовятся на все прогоны.
"""

from datetime import datetime, timezone

import pytest

from tests.performance.conftest import REPEAT_BULK, RUNS, RUNS_BULK, perf_run

pytestmark = [pytest.mark.performance, pytest.mark.asyncio]

MODULE = "Activity"


class TestActivityPerformance:

    # ── CREATE ──

    async def test_create_single(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity
        from backend.base.crm.activity.models.activity_type import ActivityType

        types = await ActivityType.search(fields=["id"], limit=1)
        type_id = types[0].id

        await perf_run(
            perf_report,
            MODULE,
            "create — single",
            1,
            lambda: Activity.create(
                Activity(
                    res_model="lead",
                    res_id=1,
                    activity_type_id=type_id,
                    user_id=1,
                    date_deadline=datetime.now(timezone.utc),
                    state="planned",
                    summary="Perf activity",
                )
            ),
        )

    async def test_create_bulk(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity
        from backend.base.crm.activity.models.activity_type import ActivityType

        types = await ActivityType.search(fields=["id"], limit=1)
        type_id = types[0].id

        n = 5_000
        batches = iter(
            [
                [
                    Activity(
                        res_model="lead",
                        res_id=(i % 1000) + 1,
                        activity_type_id=type_id,
                        user_id=(i % 100) + 1,
                        date_deadline=datetime.now(timezone.utc),
                        state="planned",
                        summary=f"Bulk activity {i}",
                    )
                    for i in range(n)
                ]
                for _ in range(RUNS_BULK)
            ]
        )

        await perf_run(
            perf_report,
            MODULE,
            f"create_bulk — {n:,}",
            n,
            lambda: Activity.create_bulk(next(batches)),
            repeat=REPEAT_BULK,
        )

    # ── READ ──

    async def test_get_single(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        await perf_run(
            perf_report,
            MODULE,
            "get — single by id",
            1,
            lambda: Activity.get(1),
        )

    async def test_search_by_user(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        async def run():
            result = await Activity.search(
                fields=["id", "summary", "state", "date_deadline"],
                filter=[("user_id", "=", 1)],
                limit=200,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report, MODULE, "search — filter user_id", 100, run
        )

    async def test_search_by_member_res_model(
        self, db_pool, seed_activities, perf_report
    ):
        """Filter by polymorphic field res_model."""
        from backend.base.crm.activity.models.activity import Activity

        async def run():
            result = await Activity.search(
                fields=["id", "summary", "state", "res_id"],
                filter=[("res_model", "=", "lead"), ("done", "=", False)],
                limit=1000,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report, MODULE, "search — filter res_model='lead'", 1000, run
        )

    async def test_search_overdue(self, db_pool, seed_activities, perf_report):
        """Find overdue activities (common dashboard query)."""
        from backend.base.crm.activity.models.activity import Activity

        await perf_run(
            perf_report,
            MODULE,
            "search — state='overdue'",
            1000,
            lambda: Activity.search(
                fields=["id", "summary", "user_id", "date_deadline"],
                filter=[("state", "=", "overdue"), ("done", "=", False)],
                limit=1000,
            ),
        )

    async def test_search_count(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        async def run():
            count = await Activity.search_count()
            assert count >= 100_000

        await perf_run(
            perf_report, MODULE, "search_count — 100k table", 100_000, run
        )

    # ── UPDATE ──

    async def test_update_single(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        act = await Activity.get(1)
        await perf_run(
            perf_report,
            MODULE,
            "update — single",
            1,
            lambda: act.update(Activity(state="done", done=True)),
        )

    async def test_update_bulk(self, db_pool, seed_activities, perf_report):
        from backend.base.crm.activity.models.activity import Activity

        n = 5_000
        ids = list(range(1, n + 1))

        await perf_run(
            perf_report,
            MODULE,
            f"update_bulk — {n:,}",
            n,
            lambda: Activity.update_bulk(
                ids, Activity(notification_sent=True)
            ),
            repeat=REPEAT_BULK,
        )

    # ── DELETE ──

    async def test_delete_single(self, db_pool, seed_activities, perf_report):
        """Своя запись с конца таблицы на каждый прогон."""
        from backend.base.crm.activity.models.activity import Activity

        acts = iter(
            [
                await Activity.get(seed_activities - i, fields=["id"])
                for i in range(RUNS)
            ]
        )
        await perf_run(
            perf_report,
            MODULE,
            "delete — single",
            1,
            lambda: next(acts).delete(),
        )

    async def test_delete_bulk(self, db_pool, seed_activities, perf_report):
        """Своя пачка id ниже одиночных на каждый прогон."""
        from backend.base.crm.activity.models.activity import Activity

        n = 2_000
        top = seed_activities - RUNS
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
            lambda: Activity.delete_bulk(next(batches)),
            repeat=REPEAT_BULK,
        )
