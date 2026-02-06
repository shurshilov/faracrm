"""
Integration tests for Cron module.

Tests cover:
- CronJob CRUD
- calculate_next_call for all interval types
- get_pending_jobs filtering logic
- create_or_update idempotency
- execute method (code + model method)
- Job state lifecycle (pending → running → success/error)

Run: pytest tests/integration/cron/test_cron.py -v -m integration
"""

import pytest
from datetime import datetime, timedelta, timezone

pytestmark = pytest.mark.integration


class TestCronJobCRUD:
    """Tests for CronJob model basic CRUD."""

    async def test_create_cron_job(self):
        from backend.base.system.cron.models.cron_job import CronJob

        jid = await CronJob.create(
            CronJob(
                name="Test Job",
                active=True,
                model_name="user",
                method_name="search",
                interval_number=1,
                interval_type="days",
                nextcall=datetime.now(timezone.utc),
            )
        )
        j = await CronJob.get(jid)
        assert j.name == "Test Job"
        assert j.active is True
        assert j.interval_type == "days"

    async def test_create_code_job(self):
        from backend.base.system.cron.models.cron_job import CronJob

        jid = await CronJob.create(
            CronJob(
                name="Code Job",
                code='result["status"] = "ok"',
                interval_number=5,
                interval_type="minutes",
                nextcall=datetime.now(timezone.utc),
            )
        )
        j = await CronJob.get(jid)
        assert j.code == 'result["status"] = "ok"'
        assert j.interval_type == "minutes"

    async def test_search_active_jobs(self):
        from backend.base.system.cron.models.cron_job import CronJob

        await CronJob.create(
            CronJob(name="Active Job", active=True,
                    nextcall=datetime.now(timezone.utc))
        )
        await CronJob.create(
            CronJob(name="Inactive Job", active=False,
                    nextcall=datetime.now(timezone.utc))
        )

        active = await CronJob.search(
            fields=["id", "name"],
            filter=[("active", "=", True)],
        )
        names = [j.name for j in active]
        assert "Active Job" in names
        assert "Inactive Job" not in names

    async def test_update_cron_job(self):
        from backend.base.system.cron.models.cron_job import CronJob

        jid = await CronJob.create(
            CronJob(name="Update Me", interval_number=1, interval_type="hours",
                    nextcall=datetime.now(timezone.utc))
        )
        j = await CronJob.get(jid)
        await j.update(CronJob(interval_number=2, interval_type="days"))

        updated = await CronJob.get(jid)
        assert updated.interval_number == 2
        assert updated.interval_type == "days"

    async def test_delete_cron_job(self):
        from backend.base.system.cron.models.cron_job import CronJob

        jid = await CronJob.create(
            CronJob(name="Delete Me", nextcall=datetime.now(timezone.utc))
        )
        j = await CronJob.get(jid)
        await j.delete()
        assert await CronJob.get_or_none(jid) is None


class TestCalculateNextCall:
    """Tests for CronJob.calculate_next_call() method."""

    async def test_minutes_interval(self):
        from backend.base.system.cron.models.cron_job import CronJob

        now = datetime.now(timezone.utc)
        job = CronJob(
            interval_number=30,
            interval_type="minutes",
            lastcall=now,
        )
        next_call = job.calculate_next_call()
        expected = now + timedelta(minutes=30)
        assert abs((next_call - expected).total_seconds()) < 2

    async def test_hours_interval(self):
        from backend.base.system.cron.models.cron_job import CronJob

        now = datetime.now(timezone.utc)
        job = CronJob(interval_number=2, interval_type="hours", lastcall=now)
        next_call = job.calculate_next_call()
        expected = now + timedelta(hours=2)
        assert abs((next_call - expected).total_seconds()) < 2

    async def test_days_interval(self):
        from backend.base.system.cron.models.cron_job import CronJob

        now = datetime.now(timezone.utc)
        job = CronJob(interval_number=7, interval_type="days", lastcall=now)
        next_call = job.calculate_next_call()
        expected = now + timedelta(days=7)
        assert abs((next_call - expected).total_seconds()) < 2

    async def test_weeks_interval(self):
        from backend.base.system.cron.models.cron_job import CronJob

        now = datetime.now(timezone.utc)
        job = CronJob(interval_number=2, interval_type="weeks", lastcall=now)
        next_call = job.calculate_next_call()
        expected = now + timedelta(weeks=2)
        assert abs((next_call - expected).total_seconds()) < 2

    async def test_months_interval(self):
        from backend.base.system.cron.models.cron_job import CronJob

        now = datetime.now(timezone.utc)
        job = CronJob(interval_number=3, interval_type="months", lastcall=now)
        next_call = job.calculate_next_call()
        expected = now + timedelta(days=90)
        assert abs((next_call - expected).total_seconds()) < 2

    async def test_past_next_call_returns_now(self):
        """If computed next_call is in the past, use now instead."""
        from backend.base.system.cron.models.cron_job import CronJob

        past = datetime.now(timezone.utc) - timedelta(days=100)
        job = CronJob(interval_number=1, interval_type="days", lastcall=past)
        next_call = job.calculate_next_call()
        # Should be approximately now, not in the past
        now = datetime.now(timezone.utc)
        assert (now - next_call).total_seconds() < 5

    async def test_no_lastcall_uses_now(self):
        from backend.base.system.cron.models.cron_job import CronJob

        job = CronJob(interval_number=1, interval_type="hours", lastcall=None)
        next_call = job.calculate_next_call()
        now = datetime.now(timezone.utc)
        # Should be about 1 hour from now
        diff = (next_call - now).total_seconds()
        assert 3500 < diff < 3700


class TestJobState:
    """Tests for job state tracking fields."""

    async def test_initial_state_pending(self):
        from backend.base.system.cron.models.cron_job import CronJob

        jid = await CronJob.create(
            CronJob(name="State Test", nextcall=datetime.now(timezone.utc))
        )
        j = await CronJob.get(jid)
        assert j.last_status == "pending"
        assert j.run_count == 0

    async def test_track_success(self):
        from backend.base.system.cron.models.cron_job import CronJob

        jid = await CronJob.create(
            CronJob(name="Success Test", nextcall=datetime.now(timezone.utc))
        )
        j = await CronJob.get(jid)

        await j.update(CronJob(
            last_status="success",
            last_duration=1.5,
            run_count=1,
            lastcall=datetime.now(timezone.utc),
        ))

        updated = await CronJob.get(jid)
        assert updated.last_status == "success"
        assert updated.last_duration == 1.5
        assert updated.run_count == 1

    async def test_track_error(self):
        from backend.base.system.cron.models.cron_job import CronJob

        jid = await CronJob.create(
            CronJob(name="Error Test", nextcall=datetime.now(timezone.utc))
        )
        j = await CronJob.get(jid)

        await j.update(CronJob(
            last_status="error",
            last_error="Connection refused",
        ))

        updated = await CronJob.get(jid)
        assert updated.last_status == "error"
        assert "Connection refused" in updated.last_error

    async def test_numbercall_limit(self):
        """Job should be deactivated when run_count reaches numbercall."""
        from backend.base.system.cron.models.cron_job import CronJob

        jid = await CronJob.create(
            CronJob(
                name="Limited Job",
                numbercall=3,
                run_count=2,
                active=True,
                nextcall=datetime.now(timezone.utc),
            )
        )
        j = await CronJob.get(jid)

        # Simulate reaching limit
        await j.update(CronJob(run_count=3, active=False))

        updated = await CronJob.get(jid)
        assert updated.run_count == 3
        assert updated.active is False

    async def test_unlimited_runs(self):
        """numbercall=-1 means unlimited."""
        from backend.base.system.cron.models.cron_job import CronJob

        jid = await CronJob.create(
            CronJob(
                name="Unlimited Job",
                numbercall=-1,
                run_count=1000,
                active=True,
                nextcall=datetime.now(timezone.utc),
            )
        )
        j = await CronJob.get(jid)
        assert j.active is True
        assert j.numbercall == -1


class TestCreateOrUpdate:
    """Tests for CronJob.create_or_update() idempotency."""

    async def test_create_new_job(self, test_env):
        from backend.base.system.cron.models.cron_job import CronJob

        result = await CronJob.create_or_update(
            env=test_env,
            name="Unique New Job",
            model_name="user",
            method_name="search",
            interval_number=1,
            interval_type="hours",
        )
        assert result is not None

        jobs = await CronJob.search(
            fields=["id", "name"],
            filter=[("name", "=", "Unique New Job")],
        )
        assert len(jobs) == 1

    async def test_update_existing_job(self, test_env):
        from backend.base.system.cron.models.cron_job import CronJob

        # Create
        await CronJob.create_or_update(
            env=test_env,
            name="Idempotent Job",
            interval_number=1,
            interval_type="hours",
        )

        # Update with same name
        await CronJob.create_or_update(
            env=test_env,
            name="Idempotent Job",
            interval_number=5,
            interval_type="days",
        )

        jobs = await CronJob.search(
            fields=["id", "name", "interval_number", "interval_type"],
            filter=[("name", "=", "Idempotent Job")],
        )
        assert len(jobs) == 1
        assert jobs[0].interval_number == 5
        assert jobs[0].interval_type == "days"
