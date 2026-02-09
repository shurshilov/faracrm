"""
ORM Comparison Benchmark: dotorm vs SQLAlchemy (async) vs Tortoise ORM

Same Activity-like model, same 100k dataset, same CRUD operations.
Each ORM creates its own table, seeds 100k rows, runs identical benchmarks.

Run:
    pip install sqlalchemy[asyncio] asyncpg tortoise-orm
    pytest tests/performance/test_orm_comparison.py -v -s --tb=short

Prerequisites:
    - PostgreSQL running on localhost:5432
    - Database 'fara_crm_test' exists (created by conftest)
"""

import os
import time
from datetime import date, datetime, timezone
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
import asyncpg

pytestmark = [pytest.mark.performance, pytest.mark.asyncio]

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "openpg")
DB_PASSWORD = os.getenv("DB_PASSWORD", "openpgpwd")
DB_NAME = os.getenv("TEST_DB_NAME", "fara_crm_test")

DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
TORTOISE_DB_URL = (
    f"asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

SEED_COUNT = 100_000
BULK_CREATE_N = 5_000
BULK_UPDATE_N = 5_000
BULK_DELETE_N = 2_000
SEARCH_LIMIT = 1_000

# ──────────────────────────────────────────────
# Result collector
# ──────────────────────────────────────────────

from tests.performance.conftest import PerfReport

_report = PerfReport()


@asynccontextmanager
async def bench(orm_name: str, operation: str, rows: int):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    _report.add(orm_name, operation, rows, elapsed)


@pytest.fixture(scope="module")
def comparison_report():
    return _report


@pytest.fixture(scope="module", autouse=True)
def _print_comparison_report(comparison_report):
    yield
    comparison_report.print_console()
    report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports")
    comparison_report.save_json(
        os.path.join(report_dir, "orm_comparison.json")
    )
    comparison_report.save_comparison_html(
        os.path.join(report_dir, "orm_comparison.html")
    )


# ══════════════════════════════════════════════
# 1) RAW asyncpg (baseline, no ORM overhead)
# ══════════════════════════════════════════════


@pytest_asyncio.fixture(scope="class")
async def raw_pool():
    pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        min_size=5,
        max_size=10,
    )
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS bench_activity_raw CASCADE")
        await conn.execute("""
            CREATE TABLE bench_activity_raw (
                id SERIAL PRIMARY KEY,
                res_model VARCHAR(255) NOT NULL,
                res_id INTEGER NOT NULL,
                summary VARCHAR(255),
                note TEXT,
                date_deadline DATE NOT NULL,
                user_id INTEGER NOT NULL,
                state VARCHAR(20) NOT NULL DEFAULT 'planned',
                done BOOLEAN NOT NULL DEFAULT false,
                active BOOLEAN NOT NULL DEFAULT true,
                notification_sent BOOLEAN NOT NULL DEFAULT false,
                create_date TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        await conn.execute("""
            CREATE INDEX idx_raw_user_id ON bench_activity_raw (user_id);
            CREATE INDEX idx_raw_date_deadline ON bench_activity_raw (date_deadline);
            CREATE INDEX idx_raw_state ON bench_activity_raw (state);
            CREATE INDEX idx_raw_done ON bench_activity_raw (done);
            CREATE INDEX idx_raw_res_model ON bench_activity_raw (res_model);
        """)
        await conn.execute(
            """
            INSERT INTO bench_activity_raw
                (res_model, res_id, summary, date_deadline, user_id, state, done,
                 notification_sent, active, create_date)
            SELECT
                CASE g % 3 WHEN 0 THEN 'lead' WHEN 1 THEN 'partner' ELSE 'task' END,
                (g % 1000) + 1,
                'Activity #' || g,
                current_date + ((g % 60) - 30),
                (g % 10000) + 1,
                CASE WHEN g%5=0 THEN 'done' WHEN g%7=0 THEN 'overdue'
                     WHEN g%3=0 THEN 'today' ELSE 'planned' END,
                (g % 5 = 0),
                false, true,
                now() - (random() * interval '90 days')
            FROM generate_series(1, $1) g
        """,
            SEED_COUNT,
        )
    yield pool
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS bench_activity_raw CASCADE")
    await pool.close()


class TestRawAsyncpg:
    """Baseline: raw asyncpg, no ORM."""

    ORM = "raw asyncpg"

    async def test_create_single(self, raw_pool):
        async with raw_pool.acquire() as conn:
            async with bench(self.ORM, "create — single", 1):
                await conn.execute(
                    """INSERT INTO bench_activity_raw
                       (res_model,res_id,summary,date_deadline,user_id,state)
                       VALUES ($1,$2,$3,$4,$5,$6)""",
                    "lead",
                    1,
                    "Bench single",
                    date.today(),
                    1,
                    "planned",
                )

    async def test_create_bulk(self, raw_pool):
        async with raw_pool.acquire() as conn:
            async with bench(
                self.ORM, f"create_bulk — {BULK_CREATE_N:,}", BULK_CREATE_N
            ):
                await conn.executemany(
                    """INSERT INTO bench_activity_raw
                       (res_model,res_id,summary,date_deadline,user_id,state)
                       VALUES ($1,$2,$3,$4,$5,$6)""",
                    [
                        (
                            "lead",
                            (i % 1000) + 1,
                            f"Bulk {i}",
                            date.today(),
                            (i % 10000) + 1,
                            "planned",
                        )
                        for i in range(BULK_CREATE_N)
                    ],
                )

    async def test_get_single(self, raw_pool):
        async with raw_pool.acquire() as conn:
            async with bench(self.ORM, "get — single by id", 1):
                await conn.fetchrow(
                    "SELECT * FROM bench_activity_raw WHERE id = $1", 1
                )

    async def test_search_filter_user(self, raw_pool):
        async with raw_pool.acquire() as conn:
            async with bench(
                self.ORM, "search — filter user_id", SEARCH_LIMIT
            ):
                rows = await conn.fetch(
                    """SELECT id,summary,state,date_deadline
                       FROM bench_activity_raw WHERE user_id=$1 LIMIT $2""",
                    1,
                    SEARCH_LIMIT,
                )

    async def test_search_filter_res_model(self, raw_pool):
        async with raw_pool.acquire() as conn:
            async with bench(
                self.ORM, "search — filter res_model='lead'", SEARCH_LIMIT
            ):
                rows = await conn.fetch(
                    """SELECT id,summary,state,res_id
                       FROM bench_activity_raw
                       WHERE res_model=$1 AND done=$2 LIMIT $3""",
                    "lead",
                    False,
                    SEARCH_LIMIT,
                )

    async def test_search_filter_state(self, raw_pool):
        async with raw_pool.acquire() as conn:
            async with bench(
                self.ORM, "search — state='overdue'", SEARCH_LIMIT
            ):
                rows = await conn.fetch(
                    """SELECT id,summary,user_id,date_deadline
                       FROM bench_activity_raw
                       WHERE state=$1 AND done=$2 LIMIT $3""",
                    "overdue",
                    False,
                    SEARCH_LIMIT,
                )

    async def test_search_count(self, raw_pool):
        async with raw_pool.acquire() as conn:
            async with bench(self.ORM, "search_count — 100k", SEED_COUNT):
                row = await conn.fetchval(
                    "SELECT count(*) FROM bench_activity_raw"
                )

    async def test_update_single(self, raw_pool):
        async with raw_pool.acquire() as conn:
            async with bench(self.ORM, "update — single", 1):
                await conn.execute(
                    "UPDATE bench_activity_raw SET state=$1, done=$2 WHERE id=$3",
                    "done",
                    True,
                    1,
                )

    async def test_update_bulk(self, raw_pool):
        ids = list(range(1, BULK_UPDATE_N + 1))
        async with raw_pool.acquire() as conn:
            async with bench(
                self.ORM, f"update_bulk — {BULK_UPDATE_N:,}", BULK_UPDATE_N
            ):
                await conn.execute(
                    "UPDATE bench_activity_raw SET notification_sent=$1 WHERE id = ANY($2::int[])",
                    True,
                    ids,
                )

    async def test_delete_single(self, raw_pool):
        async with raw_pool.acquire() as conn:
            async with bench(self.ORM, "delete — single", 1):
                await conn.execute(
                    "DELETE FROM bench_activity_raw WHERE id=$1",
                    SEED_COUNT,
                )

    async def test_delete_bulk(self, raw_pool):
        ids = list(range(SEED_COUNT - BULK_DELETE_N, SEED_COUNT))
        async with raw_pool.acquire() as conn:
            async with bench(
                self.ORM, f"delete_bulk — {BULK_DELETE_N:,}", BULK_DELETE_N
            ):
                await conn.execute(
                    "DELETE FROM bench_activity_raw WHERE id = ANY($1::int[])",
                    ids,
                )


# ══════════════════════════════════════════════
# 2) SQLAlchemy async
# ══════════════════════════════════════════════

try:
    from sqlalchemy.ext.asyncio import (
        create_async_engine,
        async_sessionmaker,
    )
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
    from sqlalchemy import (
        String,
        Integer as SAInteger,
        Boolean as SABoolean,
        Date as SADate,
        DateTime as SADateTime,
        Text as SAText,
        select,
        func,
        update as sa_update,
        delete as sa_delete,
    )

    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


if HAS_SQLALCHEMY:

    class SABase(DeclarativeBase):
        pass

    class SAActivity(SABase):
        __tablename__ = "bench_activity_sa"

        id: Mapped[int] = mapped_column(primary_key=True)
        res_model: Mapped[str] = mapped_column(String(255), index=True)
        res_id: Mapped[int] = mapped_column(SAInteger, index=True)
        summary: Mapped[str | None] = mapped_column(String(255))
        note: Mapped[str | None] = mapped_column(SAText)
        date_deadline: Mapped[date] = mapped_column(SADate, index=True)
        user_id: Mapped[int] = mapped_column(SAInteger, index=True)
        state: Mapped[str] = mapped_column(
            String(20), index=True, default="planned"
        )
        done: Mapped[bool] = mapped_column(
            SABoolean, index=True, default=False
        )
        active: Mapped[bool] = mapped_column(SABoolean, default=True)
        notification_sent: Mapped[bool] = mapped_column(
            SABoolean, default=False
        )
        create_date: Mapped[datetime] = mapped_column(
            SADateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
        )


@pytest_asyncio.fixture(scope="class")
async def sa_session():
    if not HAS_SQLALCHEMY:
        pytest.skip("SQLAlchemy not installed")

    engine = create_async_engine(DB_URL, pool_size=10, max_overflow=0)

    async with engine.begin() as conn:
        await conn.run_sync(SABase.metadata.drop_all)
        await conn.run_sync(SABase.metadata.create_all)

    # Seed via raw connection for speed
    raw_pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        min_size=2,
        max_size=5,
    )
    async with raw_pool.acquire() as conn:
        await conn.execute(f"""
            INSERT INTO bench_activity_sa
                (res_model, res_id, summary, date_deadline, user_id, state, done,
                 notification_sent, active, create_date)
            SELECT
                CASE g % 3 WHEN 0 THEN 'lead' WHEN 1 THEN 'partner' ELSE 'task' END,
                (g % 1000) + 1,
                'Activity #' || g,
                current_date + ((g % 60) - 30),
                (g % 10000) + 1,
                CASE WHEN g%5=0 THEN 'done' WHEN g%7=0 THEN 'overdue'
                     WHEN g%3=0 THEN 'today' ELSE 'planned' END,
                (g % 5 = 0),
                false, true,
                now() - (random() * interval '90 days')
            FROM generate_series(1, {SEED_COUNT}) g
        """)
    await raw_pool.close()

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield session_factory

    async with engine.begin() as conn:
        await conn.run_sync(SABase.metadata.drop_all)
    await engine.dispose()


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
class TestSQLAlchemy:
    """SQLAlchemy 2.0 async."""

    ORM = "SQLAlchemy"

    async def test_create_single(self, sa_session):
        async with sa_session() as s:
            async with bench(self.ORM, "create — single", 1):
                s.add(
                    SAActivity(
                        res_model="lead",
                        res_id=1,
                        summary="Bench single",
                        date_deadline=date.today(),
                        user_id=1,
                        state="planned",
                    )
                )
                await s.commit()

    async def test_create_bulk(self, sa_session):
        objects = [
            SAActivity(
                res_model="lead",
                res_id=(i % 1000) + 1,
                summary=f"Bulk {i}",
                date_deadline=date.today(),
                user_id=(i % 10000) + 1,
                state="planned",
            )
            for i in range(BULK_CREATE_N)
        ]
        async with sa_session() as s:
            async with bench(
                self.ORM, f"create_bulk — {BULK_CREATE_N:,}", BULK_CREATE_N
            ):
                s.add_all(objects)
                await s.commit()

    async def test_get_single(self, sa_session):
        async with sa_session() as s:
            async with bench(self.ORM, "get — single by id", 1):
                await s.get(SAActivity, 1)

    async def test_search_filter_user(self, sa_session):
        async with sa_session() as s:
            async with bench(
                self.ORM, "search — filter user_id", SEARCH_LIMIT
            ):
                result = await s.execute(
                    select(SAActivity)
                    .where(SAActivity.user_id == 1)
                    .limit(SEARCH_LIMIT)
                )
                result.scalars().all()

    async def test_search_filter_res_model(self, sa_session):
        async with sa_session() as s:
            async with bench(
                self.ORM, "search — filter res_model='lead'", SEARCH_LIMIT
            ):
                result = await s.execute(
                    select(SAActivity)
                    .where(
                        SAActivity.res_model == "lead",
                        SAActivity.done == False,
                    )
                    .limit(SEARCH_LIMIT)
                )
                result.scalars().all()

    async def test_search_filter_state(self, sa_session):
        async with sa_session() as s:
            async with bench(
                self.ORM, "search — state='overdue'", SEARCH_LIMIT
            ):
                result = await s.execute(
                    select(SAActivity)
                    .where(
                        SAActivity.state == "overdue", SAActivity.done == False
                    )
                    .limit(SEARCH_LIMIT)
                )
                result.scalars().all()

    async def test_search_count(self, sa_session):
        async with sa_session() as s:
            async with bench(self.ORM, "search_count — 100k", SEED_COUNT):
                result = await s.execute(
                    select(func.count()).select_from(SAActivity)
                )
                result.scalar()

    async def test_update_single(self, sa_session):
        async with sa_session() as s:
            obj = await s.get(SAActivity, 1)
            async with bench(self.ORM, "update — single", 1):
                obj.state = "done"
                obj.done = True
                await s.commit()

    async def test_update_bulk(self, sa_session):
        ids = list(range(1, BULK_UPDATE_N + 1))
        async with sa_session() as s:
            async with bench(
                self.ORM, f"update_bulk — {BULK_UPDATE_N:,}", BULK_UPDATE_N
            ):
                await s.execute(
                    sa_update(SAActivity)
                    .where(SAActivity.id.in_(ids))
                    .values(notification_sent=True)
                )
                await s.commit()

    async def test_delete_single(self, sa_session):
        async with sa_session() as s:
            obj = await s.get(SAActivity, SEED_COUNT)
            if obj:
                async with bench(self.ORM, "delete — single", 1):
                    await s.delete(obj)
                    await s.commit()

    async def test_delete_bulk(self, sa_session):
        ids = list(range(SEED_COUNT - BULK_DELETE_N, SEED_COUNT))
        async with sa_session() as s:
            async with bench(
                self.ORM, f"delete_bulk — {BULK_DELETE_N:,}", BULK_DELETE_N
            ):
                await s.execute(
                    sa_delete(SAActivity).where(SAActivity.id.in_(ids))
                )
                await s.commit()


# ══════════════════════════════════════════════
# 3) Tortoise ORM
# ══════════════════════════════════════════════

try:
    from tortoise import Tortoise, fields
    from tortoise.models import Model as TortoiseModel

    HAS_TORTOISE = True
except ImportError:
    HAS_TORTOISE = False


if HAS_TORTOISE:

    class TortoiseActivity(TortoiseModel):
        id = fields.IntField(pk=True)
        res_model = fields.CharField(max_length=255, index=True)
        res_id = fields.IntField(index=True)
        summary = fields.CharField(max_length=255, null=True)
        note = fields.TextField(null=True)
        date_deadline = fields.DateField(index=True)
        user_id = fields.IntField(index=True)
        state = fields.CharField(max_length=20, default="planned", index=True)
        done = fields.BooleanField(default=False, index=True)
        active = fields.BooleanField(default=True)
        notification_sent = fields.BooleanField(default=False)
        create_date = fields.DatetimeField(auto_now_add=True)

        class Meta:
            table = "bench_activity_tortoise"


@pytest_asyncio.fixture(scope="class")
async def tortoise_db():
    if not HAS_TORTOISE:
        pytest.skip("Tortoise ORM not installed")

    await Tortoise.init(
        db_url=TORTOISE_DB_URL,
        modules={"models": ["tests.performance.test_orm_comparison"]},
    )
    await Tortoise.generate_schemas(safe=True)

    # Seed via raw asyncpg
    raw_pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        min_size=2,
        max_size=5,
    )
    async with raw_pool.acquire() as conn:
        await conn.execute(f"""
            INSERT INTO bench_activity_tortoise
                (res_model, res_id, summary, date_deadline, user_id, state, done,
                 notification_sent, active, create_date)
            SELECT
                CASE g % 3 WHEN 0 THEN 'lead' WHEN 1 THEN 'partner' ELSE 'task' END,
                (g % 1000) + 1,
                'Activity #' || g,
                current_date + ((g % 60) - 30),
                (g % 10000) + 1,
                CASE WHEN g%5=0 THEN 'done' WHEN g%7=0 THEN 'overdue'
                     WHEN g%3=0 THEN 'today' ELSE 'planned' END,
                (g % 5 = 0),
                false, true,
                now() - (random() * interval '90 days')
            FROM generate_series(1, {SEED_COUNT}) g
        """)
    await raw_pool.close()

    yield

    await Tortoise.close_connections()
    # Cleanup table
    clean_pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        min_size=1,
        max_size=2,
    )
    async with clean_pool.acquire() as conn:
        await conn.execute(
            "DROP TABLE IF EXISTS bench_activity_tortoise CASCADE"
        )
    await clean_pool.close()


@pytest.mark.skipif(not HAS_TORTOISE, reason="Tortoise ORM not installed")
class TestTortoise:
    """Tortoise ORM."""

    ORM = "Tortoise"

    async def test_create_single(self, tortoise_db):
        async with bench(self.ORM, "create — single", 1):
            await TortoiseActivity.create(
                res_model="lead",
                res_id=1,
                summary="Bench single",
                date_deadline=date.today(),
                user_id=1,
                state="planned",
            )

    async def test_create_bulk(self, tortoise_db):
        objects = [
            TortoiseActivity(
                res_model="lead",
                res_id=(i % 1000) + 1,
                summary=f"Bulk {i}",
                date_deadline=date.today(),
                user_id=(i % 10000) + 1,
                state="planned",
            )
            for i in range(BULK_CREATE_N)
        ]
        async with bench(
            self.ORM, f"create_bulk — {BULK_CREATE_N:,}", BULK_CREATE_N
        ):
            await TortoiseActivity.bulk_create(objects, batch_size=1000)

    async def test_get_single(self, tortoise_db):
        async with bench(self.ORM, "get — single by id", 1):
            await TortoiseActivity.get(id=1)

    async def test_search_filter_user(self, tortoise_db):
        async with bench(self.ORM, "search — filter user_id", SEARCH_LIMIT):
            rows = (
                await TortoiseActivity.filter(user_id=1)
                .limit(SEARCH_LIMIT)
                .all()
            )

    async def test_search_filter_res_model(self, tortoise_db):
        async with bench(
            self.ORM, "search — filter res_model='lead'", SEARCH_LIMIT
        ):
            rows = await (
                TortoiseActivity.filter(res_model="lead", done=False)
                .limit(SEARCH_LIMIT)
                .all()
            )

    async def test_search_filter_state(self, tortoise_db):
        async with bench(self.ORM, "search — state='overdue'", SEARCH_LIMIT):
            rows = await (
                TortoiseActivity.filter(state="overdue", done=False)
                .limit(SEARCH_LIMIT)
                .all()
            )

    async def test_search_count(self, tortoise_db):
        async with bench(self.ORM, "search_count — 100k", SEED_COUNT):
            await TortoiseActivity.all().count()

    async def test_update_single(self, tortoise_db):
        obj = await TortoiseActivity.get(id=1)
        async with bench(self.ORM, "update — single", 1):
            obj.state = "done"
            obj.done = True
            await obj.save()

    async def test_update_bulk(self, tortoise_db):
        ids = list(range(1, BULK_UPDATE_N + 1))
        async with bench(
            self.ORM, f"update_bulk — {BULK_UPDATE_N:,}", BULK_UPDATE_N
        ):
            await TortoiseActivity.filter(id__in=ids).update(
                notification_sent=True
            )

    async def test_delete_single(self, tortoise_db):
        obj = await TortoiseActivity.get(id=SEED_COUNT)
        async with bench(self.ORM, "delete — single", 1):
            await obj.delete()

    async def test_delete_bulk(self, tortoise_db):
        ids = list(range(SEED_COUNT - BULK_DELETE_N, SEED_COUNT))
        async with bench(
            self.ORM, f"delete_bulk — {BULK_DELETE_N:,}", BULK_DELETE_N
        ):
            await TortoiseActivity.filter(id__in=ids).delete()


# ══════════════════════════════════════════════
# 4) dotorm (our ORM)
# ══════════════════════════════════════════════


@pytest_asyncio.fixture(scope="class")
async def dotorm_ready(db_pool):
    """Seed activity table for dotorm benchmarks (reuses existing schema)."""
    from backend.base.crm.languages.models.language import Language

    async with db_pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE activity, activity_type, users, language CASCADE"
        )

    lang_id = await Language.create(
        Language(code="en", name="English", active=True)
    )

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (name, login, password_hash, password_salt, is_admin, lang_id)
            SELECT 'User ' || g, 'user_' || g, 'h', 's', false, $1
            FROM generate_series(1, 10000) g
        """,
            lang_id,
        )

        await conn.execute("""
            INSERT INTO activity_type (name, active, default_days, icon)
            VALUES ('Call', true, 1, 'phone'), ('Email', true, 2, 'mail'),
                   ('Meeting', true, 3, 'calendar'), ('Task', true, 5, 'check')
        """)

        await conn.execute(
            """
            INSERT INTO activity
                (res_model, res_id, activity_type_id, user_id, date_deadline,
                 state, done, notification_sent, active, create_date, summary)
            SELECT
                CASE g%3 WHEN 0 THEN 'lead' WHEN 1 THEN 'partner' ELSE 'task' END,
                (g % 1000) + 1,
                (g % 4) + (SELECT min(id) FROM activity_type),
                (g % 10000) + 1,
                current_date + ((g % 60) - 30),
                CASE WHEN g%5=0 THEN 'done' WHEN g%7=0 THEN 'overdue'
                     WHEN g%3=0 THEN 'today' ELSE 'planned' END,
                (g % 5 = 0),
                false, true,
                now() - (random() * interval '90 days'),
                'Activity #' || g
            FROM generate_series(1, $1) g
        """,
            SEED_COUNT,
        )
    yield


class TestDotorm:
    """dotorm (FARA CRM ORM)."""

    ORM = "dotorm"

    async def test_create_single(
        self, db_pool, dotorm_ready, comparison_report
    ):
        from backend.base.crm.activity.models.activity import Activity
        from backend.base.crm.activity.models.activity_type import ActivityType

        types = await ActivityType.search(fields=["id"], limit=1)

        async with bench(self.ORM, "create — single", 1):
            await Activity.create(
                Activity(
                    res_model="lead",
                    res_id=1,
                    summary="Bench single",
                    date_deadline=date.today(),
                    user_id=1,
                    activity_type_id=types[0].id,
                    state="planned",
                )
            )

    async def test_create_bulk(self, db_pool, dotorm_ready, comparison_report):
        from backend.base.crm.activity.models.activity import Activity
        from backend.base.crm.activity.models.activity_type import ActivityType
        from tests.performance.conftest import chunked_create_bulk

        types = await ActivityType.search(fields=["id"], limit=1)
        type_id = types[0].id

        payload = [
            Activity(
                res_model="lead",
                res_id=(i % 1000) + 1,
                summary=f"Bulk {i}",
                date_deadline=date.today(),
                user_id=(i % 10000) + 1,
                activity_type_id=type_id,
                state="planned",
            )
            for i in range(BULK_CREATE_N)
        ]

        async with bench(
            self.ORM, f"create_bulk — {BULK_CREATE_N:,}", BULK_CREATE_N
        ):
            await chunked_create_bulk(Activity, payload)

    async def test_get_single(self, db_pool, dotorm_ready, comparison_report):
        from backend.base.crm.activity.models.activity import Activity

        async with bench(self.ORM, "get — single by id", 1):
            await Activity.get(1)

    async def test_search_filter_user(
        self, db_pool, dotorm_ready, comparison_report
    ):
        from backend.base.crm.activity.models.activity import Activity

        async with bench(self.ORM, "search — filter user_id", SEARCH_LIMIT):
            await Activity.search(
                fields=["id", "summary", "state", "date_deadline"],
                filter=[("user_id", "=", 1)],
                limit=SEARCH_LIMIT,
            )

    async def test_search_filter_res_model(
        self, db_pool, dotorm_ready, comparison_report
    ):
        from backend.base.crm.activity.models.activity import Activity

        async with bench(
            self.ORM, "search — filter res_model='lead'", SEARCH_LIMIT
        ):
            await Activity.search(
                fields=["id", "summary", "state", "res_id"],
                filter=[("res_model", "=", "lead"), ("done", "=", False)],
                limit=SEARCH_LIMIT,
            )

    async def test_search_filter_state(
        self, db_pool, dotorm_ready, comparison_report
    ):
        from backend.base.crm.activity.models.activity import Activity

        async with bench(self.ORM, "search — state='overdue'", SEARCH_LIMIT):
            await Activity.search(
                fields=["id", "summary", "user_id", "date_deadline"],
                filter=[("state", "=", "overdue"), ("done", "=", False)],
                limit=SEARCH_LIMIT,
            )

    async def test_search_count(
        self, db_pool, dotorm_ready, comparison_report
    ):
        from backend.base.crm.activity.models.activity import Activity

        async with bench(self.ORM, "search_count — 100k", SEED_COUNT):
            await Activity.search_count()

    async def test_update_single(
        self, db_pool, dotorm_ready, comparison_report
    ):
        from backend.base.crm.activity.models.activity import Activity

        obj = await Activity.get(1)
        async with bench(self.ORM, "update — single", 1):
            await obj.update(Activity(state="done", done=True))

    async def test_update_bulk(self, db_pool, dotorm_ready, comparison_report):
        from backend.base.crm.activity.models.activity import Activity

        ids = list(range(1, BULK_UPDATE_N + 1))
        async with bench(
            self.ORM, f"update_bulk — {BULK_UPDATE_N:,}", BULK_UPDATE_N
        ):
            await Activity.update_bulk(ids, Activity(notification_sent=True))

    async def test_delete_single(
        self, db_pool, dotorm_ready, comparison_report
    ):
        from backend.base.crm.activity.models.activity import Activity

        obj = await Activity.get(SEED_COUNT)
        async with bench(self.ORM, "delete — single", 1):
            await obj.delete()

    async def test_delete_bulk(self, db_pool, dotorm_ready, comparison_report):
        from backend.base.crm.activity.models.activity import Activity

        ids = list(range(SEED_COUNT - BULK_DELETE_N, SEED_COUNT))
        async with bench(
            self.ORM, f"delete_bulk — {BULK_DELETE_N:,}", BULK_DELETE_N
        ):
            await Activity.delete_bulk(ids)
