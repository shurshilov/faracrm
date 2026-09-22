"""
Performance: Leads (100 000 rows)

CRUD benchmarks on leads table with stage FK.

Каждая операция гоняется WARMUP + REPEAT (массовые — REPEAT_BULK) раз, см.
conftest.perf_run; удаляемые записи готовятся на все прогоны.
"""

import pytest

from tests.performance.conftest import REPEAT_BULK, RUNS, RUNS_BULK, perf_run

pytestmark = [pytest.mark.performance, pytest.mark.asyncio]

MODULE = "Leads"


class TestLeadPerformance:

    # ── CREATE ──

    async def test_create_single(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        stages = await LeadStage.search(fields=["id"], limit=1)
        stage_id = stages[0].id

        await perf_run(
            perf_report,
            MODULE,
            "create — single",
            1,
            lambda: Lead.create(
                Lead(
                    name="Perf Lead",
                    stage_id=stage_id,
                    user_id=1,
                    type="lead",
                )
            ),
        )

    async def test_create_bulk(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        stages = await LeadStage.search(fields=["id"], limit=1)
        stage_id = stages[0].id

        n = 5_000
        batches = iter(
            [
                [
                    Lead(
                        name=f"Bulk Lead {i}",
                        stage_id=stage_id,
                        user_id=(i % 100) + 1,
                        type="lead",
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
            lambda: Lead.create_bulk(next(batches)),
            repeat=REPEAT_BULK,
        )

    # ── READ ──

    async def test_get_single(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        await perf_run(
            perf_report, MODULE, "get — single by id", 1, lambda: Lead.get(1)
        )

    async def test_search_limit_100(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        n = 100

        async def run():
            result = await Lead.search(
                fields=["id", "name", "stage_id", "type", "website"],
                limit=n,
            )
            assert len(result) == n

        await perf_run(perf_report, MODULE, f"search — limit {n}", n, run)

    async def test_search_limit_10000(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        n = 10_000

        async def run():
            result = await Lead.search(
                fields=["id", "name", "stage_id", "type"],
                limit=n,
            )
            assert len(result) == n

        await perf_run(perf_report, MODULE, f"search — limit {n:,}", n, run)

    async def test_search_filter_type(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        async def run():
            result = await Lead.search(
                fields=["id", "name", "website"],
                filter=[("type", "=", "opportunity")],
                limit=1000,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report,
            MODULE,
            "search — filter type='opportunity'",
            1000,
            run,
        )

    async def test_search_filter_user(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        async def run():
            result = await Lead.search(
                fields=["id", "name", "type"],
                filter=[("user_id", "=", 1)],
                limit=200,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report, MODULE, "search — filter user_id", 200, run
        )

    async def test_search_filter_combined(
        self, db_pool, seed_leads, perf_report
    ):
        """Combined filter: type + active + user_id."""
        from backend.base.crm.leads.models.leads import Lead

        await perf_run(
            perf_report,
            MODULE,
            "search — multi-filter (type+active+user)",
            200,
            lambda: Lead.search(
                fields=["id", "name", "type", "website"],
                filter=[
                    ("type", "=", "lead"),
                    ("active", "=", True),
                    ("user_id", "=", 1),
                ],
                limit=200,
            ),
        )

    async def test_search_filter_name_ilike(
        self, db_pool, seed_leads, perf_report
    ):
        """Text search: name ilike on 100k rows (email у лида больше нет)."""
        from backend.base.crm.leads.models.leads import Lead

        async def run():
            # ilike = подстрока: %…% и экранирование добавляет парсер
            result = await Lead.search(
                fields=["id", "name"],
                filter=[("name", "ilike", "500")],
                limit=100,
            )
            assert len(result) >= 1

        await perf_run(
            perf_report, MODULE, "search — name ilike '500'", 100, run
        )

    async def test_search_count(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        async def run():
            count = await Lead.search_count()
            assert count >= 100_000

        await perf_run(
            perf_report, MODULE, "search_count — 100k table", 100_000, run
        )

    # ── UPDATE ──

    async def test_update_single(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        lead = await Lead.get(1)
        await perf_run(
            perf_report,
            MODULE,
            "update — single",
            1,
            lambda: lead.update(Lead(name="Updated Lead")),
        )

    async def test_update_bulk(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        n = 5_000
        ids = list(range(1, n + 1))

        await perf_run(
            perf_report,
            MODULE,
            f"update_bulk — {n:,}",
            n,
            lambda: Lead.update_bulk(ids, Lead(active=False)),
            repeat=REPEAT_BULK,
        )

    # ── DELETE ──

    async def test_delete_single(self, db_pool, seed_leads, perf_report):
        """Своя запись с конца таблицы на каждый прогон."""
        from backend.base.crm.leads.models.leads import Lead

        leads = iter(
            [
                await Lead.get(seed_leads - i, fields=["id"])
                for i in range(RUNS)
            ]
        )
        await perf_run(
            perf_report,
            MODULE,
            "delete — single",
            1,
            lambda: next(leads).delete(),
        )

    async def test_delete_bulk(self, db_pool, seed_leads, perf_report):
        """Своя пачка id ниже одиночных на каждый прогон."""
        from backend.base.crm.leads.models.leads import Lead

        n = 2_000
        top = seed_leads - RUNS
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
            lambda: Lead.delete_bulk(next(batches)),
            repeat=REPEAT_BULK,
        )
