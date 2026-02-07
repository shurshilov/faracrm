"""
Performance: Leads (100 000 rows)

CRUD benchmarks on leads table with stage FK.
"""

import pytest

from tests.performance.conftest import perf_timer, chunked_create_bulk

pytestmark = [pytest.mark.performance, pytest.mark.asyncio]

MODULE = "Leads"


class TestLeadPerformance:

    # ── CREATE ──

    async def test_create_single(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        stages = await LeadStage.search(fields=["id"], limit=1)
        stage_id = stages[0].id

        async with perf_timer(perf_report, MODULE, "create — single", 1):
            await Lead.create(
                Lead(
                    name="Perf Lead",
                    stage_id=stage_id,
                    user_id=1,
                    type="lead",
                    email="perf@test.com",
                )
            )

    async def test_create_bulk(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.leads.models.lead_stage import LeadStage

        stages = await LeadStage.search(fields=["id"], limit=1)
        stage_id = stages[0].id

        n = 5_000
        payload = [
            Lead(
                name=f"Bulk Lead {i}",
                stage_id=stage_id,
                user_id=(i % 100) + 1,
                type="lead",
                email=f"bulk_lead_{i}@test.com",
            )
            for i in range(n)
        ]

        async with perf_timer(perf_report, MODULE, f"create_bulk — {n:,}", n):
            await chunked_create_bulk(Lead, payload)

    # ── READ ──

    async def test_get_single(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        async with perf_timer(perf_report, MODULE, "get — single by id", 1):
            await Lead.get(1)

    async def test_search_limit_100(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        n = 100
        async with perf_timer(perf_report, MODULE, f"search — limit {n}", n):
            result = await Lead.search(
                fields=["id", "name", "stage_id", "type", "email"],
                limit=n,
            )
        assert len(result) == n

    async def test_search_limit_10000(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        n = 10_000
        async with perf_timer(perf_report, MODULE, f"search — limit {n:,}", n):
            result = await Lead.search(
                fields=["id", "name", "stage_id", "type"],
                limit=n,
            )
        assert len(result) == n

    async def test_search_filter_type(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        async with perf_timer(
            perf_report, MODULE, "search — filter type='opportunity'", 1000
        ):
            result = await Lead.search(
                fields=["id", "name", "email"],
                filter=[("type", "=", "opportunity")],
                limit=1000,
            )
        assert len(result) >= 1

    async def test_search_filter_user(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        async with perf_timer(
            perf_report, MODULE, "search — filter user_id", 200
        ):
            result = await Lead.search(
                fields=["id", "name", "type"],
                filter=[("user_id", "=", 1)],
                limit=200,
            )
        assert len(result) >= 1

    async def test_search_filter_combined(self, db_pool, seed_leads, perf_report):
        """Combined filter: type + active + user_id."""
        from backend.base.crm.leads.models.leads import Lead

        async with perf_timer(
            perf_report, MODULE, "search — multi-filter (type+active+user)", 200
        ):
            result = await Lead.search(
                fields=["id", "name", "type", "email"],
                filter=[
                    ("type", "=", "lead"),
                    ("active", "=", True),
                    ("user_id", "=", 1),
                ],
                limit=200,
            )

    async def test_search_filter_email_ilike(self, db_pool, seed_leads, perf_report):
        """Text search: email ilike on 100k rows."""
        from backend.base.crm.leads.models.leads import Lead

        async with perf_timer(
            perf_report, MODULE, "search — email ilike '%500%'", 100
        ):
            result = await Lead.search(
                fields=["id", "name", "email"],
                filter=[("email", "ilike", "%500%")],
                limit=100,
            )

    async def test_search_count(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        async with perf_timer(
            perf_report, MODULE, "search_count — 100k table", 100_000
        ):
            count = await Lead.search_count()
        assert count >= 100_000

    # ── UPDATE ──

    async def test_update_single(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        lead = await Lead.get(1)
        async with perf_timer(perf_report, MODULE, "update — single", 1):
            await lead.update(Lead(name="Updated Lead"))

    async def test_update_bulk(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        n = 5_000
        ids = list(range(1, n + 1))

        async with perf_timer(perf_report, MODULE, f"update_bulk — {n:,}", n):
            await Lead.update_bulk(ids, Lead(active=False))

    # ── DELETE ──

    async def test_delete_single(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        lead = await Lead.get(seed_leads)
        async with perf_timer(perf_report, MODULE, "delete — single", 1):
            await lead.delete()

    async def test_delete_bulk(self, db_pool, seed_leads, perf_report):
        from backend.base.crm.leads.models.leads import Lead

        n = 2_000
        start = seed_leads - n
        ids = list(range(start, seed_leads))

        async with perf_timer(perf_report, MODULE, f"delete_bulk — {n:,}", n):
            await Lead.delete_bulk(ids)
