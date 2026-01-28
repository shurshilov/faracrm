"""
Pytest configuration for integration tests.

Run with: pytest tests/integration/ -v -m integration
"""

import pytest
import pytest_asyncio

try:
    import asyncpg
except ImportError:
    asyncpg = None

from dotorm.databases.postgres.session import NoTransactionSession
from dotorm.databases.postgres.transaction import ContainerTransaction


# ====================
# Database configuration
# ====================

TEST_DB_NAME = "dotorm_test"
DB_HOST = "127.0.0.1"
DB_PORT = 5432
DB_USER = "openpg"
DB_PASSWORD = "openpgpwd"


# ====================
# Sync helpers (run in separate loop)
# ====================


def _run_sync(coro):
    """Run coroutine in new event loop."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _ensure_database():
    """Create test database if not exists."""
    conn = await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
            print(f"\n✓ Created database: {TEST_DB_NAME}")
    finally:
        await conn.close()


async def _drop_database():
    """Drop test database."""
    conn = await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database="postgres",
    )
    try:
        await conn.execute(
            f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{TEST_DB_NAME}'
            AND pid <> pg_backend_pid()
        """
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
        print(f"\n✓ Dropped database: {TEST_DB_NAME}")
    finally:
        await conn.close()


# ====================
# Session-level sync fixtures for DB lifecycle
# ====================


@pytest.fixture(scope="session", autouse=True)
def manage_database():
    """Create DB at session start, drop at end."""
    _run_sync(_ensure_database())
    yield
    _run_sync(_drop_database())


# ====================
# Module state for tables
# ====================

_tables_created = False


# ====================
# Async fixtures (function-scoped, same loop as test)
# ====================


@pytest_asyncio.fixture
async def db_pool(manage_database):
    """
    Create pool for each test.
    Pool is created in same event loop as test.
    """
    global _tables_created

    from .models import MODELS_CREATION_ORDER
    from dotorm.builder.builder import Builder

    # Создаём pool
    pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=TEST_DB_NAME,
        min_size=1,
        max_size=5,
        command_timeout=60,
    )

    # Настраиваем модели
    for model in MODELS_CREATION_ORDER:
        model._pool = pool
        model._no_transaction = NoTransactionSession
        model._builder = Builder(
            table=model.__table__,
            fields=model.get_fields(),
            dialect=model._dialect,
        )

    # Создаём таблицы только один раз
    if not _tables_created:
        async with ContainerTransaction(pool) as session:
            stmt_foreign_keys = []
            for model in MODELS_CREATION_ORDER:
                foreign_keys = await model.__create_table__(session)
                stmt_foreign_keys += foreign_keys

            for stmt_fk in stmt_foreign_keys:
                try:
                    await session.execute(stmt_fk)
                except asyncpg.exceptions.DuplicateObjectError:
                    pass

        _tables_created = True
        print(f"✓ Tables created ({len(MODELS_CREATION_ORDER)} models)")

    yield pool

    # Cleanup
    await pool.close()


@pytest_asyncio.fixture
async def session(db_pool):
    """Get session for test."""
    return NoTransactionSession(db_pool)


@pytest_asyncio.fixture
async def setup_models(db_pool):
    """Return configured models list."""
    from .models import MODELS_CREATION_ORDER

    return MODELS_CREATION_ORDER


@pytest_asyncio.fixture
async def clean_tables(db_pool, setup_models):
    """Clean all tables before test."""
    from .models import MODELS_CREATION_ORDER

    session = NoTransactionSession(db_pool)
    for model in reversed(MODELS_CREATION_ORDER):
        try:
            await session.execute(f"TRUNCATE TABLE {model.__table__} CASCADE")
        except Exception:
            pass

    yield


@pytest_asyncio.fixture
async def transaction(db_pool):
    """Transaction context manager."""
    return ContainerTransaction(db_pool)


@pytest_asyncio.fixture
async def sample_data(db_pool, clean_tables):
    """Create sample data for tests."""
    from .models import Model, Role, User, Attachment

    model1_id = await Model.create(Model(name="users"))
    model2_id = await Model.create(Model(name="roles"))

    role_admin_id = await Role.create(Role(name="admin", model_id=model1_id))
    role_user_id = await Role.create(Role(name="user", model_id=model1_id))

    user1_id = await User.create(
        User(
            name="John Doe",
            login="john",
            email="john@example.com",
            password_hash="hash123",
            password_salt="salt123",
        )
    )
    user2_id = await User.create(
        User(
            name="Jane Smith",
            login="jane",
            email="jane@example.com",
            password_hash="hash456",
            password_salt="salt456",
        )
    )

    attachment_id = await Attachment.create(
        Attachment(
            name="avatar.png",
            mimetype="image/png",
            size=1024,
            public=True,
        )
    )

    return {
        "models": [model1_id, model2_id],
        "roles": [role_admin_id, role_user_id],
        "users": [user1_id, user2_id],
        "attachments": [attachment_id],
    }
