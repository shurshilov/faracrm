"""
Pytest configuration for Fara CRM tests.

This module provides fixtures for:
- Test database creation and cleanup
- FastAPI TestClient setup
- Common test data factories
- Authentication helpers

Run tests:
    pytest tests/ -v                    # All tests
    pytest tests/unit/ -v -m unit       # Unit tests only
    pytest tests/integration/ -v -m integration  # Integration tests only
    pytest --cov=backend --cov-report=html  # With coverage
"""

import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from backend.base.crm.users.models.users import SYSTEM_USER_ID
from backend.base.crm.security.models.sessions import SystemSession
from backend.base.system.dotorm.dotorm.access import set_access_session

# Check for asyncpg
try:
    import asyncpg
except ImportError:
    asyncpg = None

# Check for httpx (for async client)
try:
    from httpx import AsyncClient, ASGITransport
except ImportError:
    AsyncClient = None
    ASGITransport = None


# ====================
# Configuration
# ====================

TEST_DB_NAME = os.getenv("TEST_DB_NAME", "fara_crm_test")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "openpg")
DB_PASSWORD = os.getenv("DB_PASSWORD", "openpgpwd")


# ====================
# Module state
# ====================

_tables_created = False
_pool = None
_models_instance = None

# ====================
# Database lifecycle
# ====================


async def _ensure_database():
    """Create test database if not exists."""
    if asyncpg is None:
        pytest.skip("asyncpg not installed")
        return

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
            print(f"\n✓ Created test database: {TEST_DB_NAME}")
    finally:
        await conn.close()


async def _drop_database():
    """Drop test database."""
    if asyncpg is None:
        return

    conn = await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database="postgres",
    )
    try:
        # Terminate all connections
        await conn.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{TEST_DB_NAME}'
            AND pid <> pg_backend_pid()
        """)
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
        print(f"\n✓ Dropped test database: {TEST_DB_NAME}")
    finally:
        await conn.close()


# ====================
# Session-scoped fixtures
# ====================


@pytest.fixture(scope="session", autouse=True)
async def manage_test_database():
    """Create test database at session start, drop at end."""
    if asyncpg is None:
        pytest.skip("asyncpg not installed")
        return

    await _ensure_database()
    yield
    await _drop_database()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def db_pool(manage_test_database) -> AsyncGenerator:
    """
    Create database pool for tests.

    Tables are created once per test session.
    Pool is created fresh for each test to ensure isolation.
    """
    global _tables_created, _pool

    if asyncpg is None:
        pytest.skip("asyncpg not installed")
        return

    pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=TEST_DB_NAME,
        min_size=5,
        max_size=10,
        command_timeout=60,
    )
    _pool = pool
    # set_access_session(session)
    set_access_session(SystemSession(user_id=SYSTEM_USER_ID))

    # Create tables if needed (first test run)
    if not _tables_created:
        await _create_all_tables(pool)
        _tables_created = True

    yield pool

    await pool.close()


# @pytest_asyncio.fixture(autouse=True)
# async def clean_all_tables(db_pool):
#     """Truncate all tables in correct order."""
#     # Order matters due to foreign keys
#     if _models_instance is not None:
#         tables_to_clean = [m.__table__ for m in _models_instance._get_models()]


#         async with _pool.acquire() as conn:
#             for table in tables_to_clean:
#                 try:
#                     await conn.execute(f"TRUNCATE TABLE {table} CASCADE")
#                 except asyncpg.exceptions.UndefinedTableError:
#                     print(f"\nX Error clean table: {table}")
#                     pass  # Table doesn't exist yet
@pytest_asyncio.fixture(autouse=True)
async def clean_all_tables(db_pool):
    """Truncate all tables in one fast query."""
    if _models_instance is not None:
        tables = [m.__table__ for m in _models_instance._get_models()]

        if tables:
            try:
                tables_str = ", ".join(tables)
                async with db_pool.acquire() as conn:
                    # Отключаем проверку FK, очищаем, включаем обратно
                    # await conn.execute(
                    #     "SET session_replication_role = 'replica'"
                    # )
                    await conn.execute(f"TRUNCATE TABLE {tables_str} CASCADE")
                    # await conn.execute(
                    #     "SET session_replication_role = 'origin'"
                    # )
            except asyncpg.exceptions.UndefinedTableError:
                print(f"\nX Error clean table: {tables_str}")
                pass  # Table doesn't exist yet


async def _create_all_tables(pool):
    """Create all application tables."""
    from backend.base.system.dotorm.dotorm.databases.postgres.session import (
        NoTransactionSession,
    )
    from backend.base.system.dotorm.dotorm.databases.postgres.transaction import (
        ContainerTransaction,
    )
    from backend.base.system.dotorm.dotorm.builder.builder import Builder
    from backend.base.system.dotorm.dotorm.components import POSTGRES

    # Import all models
    from backend.project_setup import Models

    global _tables_created, _models_instance

    models_instance = Models()
    _models_instance = models_instance
    all_models = models_instance._get_models()

    # Configure models
    for model in all_models:
        model._pool = pool
        model._no_transaction = NoTransactionSession
        model._dialect = POSTGRES
        model._builder = Builder(
            table=model.__table__,
            fields=model.get_fields(),
            dialect=POSTGRES,
        )

    # Create tables
    # Создаём таблицы только один раз
    if not _tables_created:
        async with ContainerTransaction(pool) as session:
            stmt_foreign_keys = []
            for model in all_models:
                try:
                    foreign_keys = await model.__create_table__(session)
                    stmt_foreign_keys += foreign_keys
                except Exception as e:
                    print(f"Warning: Could not create table for {model}: {e}")

            if not stmt_foreign_keys:
                return

            # Дедупликация по имени FK (M2M таблицы могут дублироваться)
            unique_fks = {
                fk_name: fk_sql for fk_name, fk_sql in stmt_foreign_keys
            }

            # Получаем существующие FK одним запросом
            existing_fk_result = await session.execute(
                "SELECT conname FROM pg_constraint WHERE contype = 'f'"
            )
            existing_fk_names = {row["conname"] for row in existing_fk_result}

            # Создаём только отсутствующие FK
            for fk_name, fk_sql in unique_fks.items():
                if fk_name not in existing_fk_names:
                    await session.execute(fk_sql)

            # Add foreign keys
            # for stmt_fk in stmt_foreign_keys:
            #     try:
            #         await session.execute(stmt_fk)
            #     except asyncpg.exceptions.DuplicateObjectError:
            #         pass
        _tables_created = True
        print(f"\n✓ Created {len(all_models)} tables")


# ====================
# Environment fixture
# ====================


@pytest_asyncio.fixture
async def test_env(db_pool):
    """
    Create test environment with configured models.

    This fixture sets up the environment similar to production
    but using the test database.
    """
    from backend.base.system.core.enviroment import Environment
    from backend.project_setup import Models, Apps, Settings
    from backend.base.system.dotorm.dotorm.databases.postgres.session import (
        NoTransactionSession,
    )
    from backend.base.system.dotorm.dotorm.builder.builder import Builder
    from backend.base.system.dotorm.dotorm.components import POSTGRES

    # Create test environment
    env = Environment()

    # Mock settings for test
    class TestSettings(Settings):
        class Config:
            env_file = ".env"

    try:
        env.settings = TestSettings()
    except Exception:
        # Use default if .env.test doesn't exist
        env.settings = Settings()

    # Setup models
    models = Models()
    for model in models._get_models():
        # if attr_name.startswith("_"):
        #     continue
        # model = getattr(models, attr_name)
        if hasattr(model, "__table__"):
            model._pool = db_pool
            model._no_transaction = NoTransactionSession
            model._dialect = POSTGRES
            model._builder = Builder(
                table=model.__table__,
                fields=model.get_fields(),
                dialect=POSTGRES,
            )

    env.models = models._build_table_mapping()
    env.apps = Apps()

    # Mock database service
    env.apps.db = MagicMock()
    env.apps.db.get_session = lambda: NoTransactionSession(db_pool)
    env.apps.db.get_pool = lambda: db_pool
    env.apps.db.fara = db_pool

    yield env


# ====================
# FastAPI test client fixtures
# ====================


@pytest_asyncio.fixture
async def app(test_env):
    """Create FastAPI application for testing."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI()
    app.state.env = test_env

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Load routers
    # await test_env.load_routers(app)
    await test_env.setup_services()
    await test_env.start_services_before(app)
    await test_env.load_routers(app)
    await test_env.start_services_after(app)
    test_env.add_handlers_errors(app)

    yield app

    # Cleanup: stop services to release PubSub LISTEN connection
    await test_env.stop_services(app)


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator:
    """Create async HTTP client for API testing."""
    if AsyncClient is None:
        pytest.skip("httpx not installed")
        return

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def authenticated_client(client, test_env) -> AsyncGenerator:
    """Create authenticated client with test user."""
    # Create test user
    from backend.base.crm.users.models.users import User
    from backend.base.crm.languages.models.language import Language

    # Create language first
    lang_id = await Language.create(
        Language(
            code="en",
            name="English",
            active=True,
        )
    )

    # Create user with password
    user = User(
        name="Test User",
        login="testuser",
        password_hash="test_hash",
        password_salt="test_salt",
        lang_id=lang_id,
    )
    user_id = await User.create(user)

    # Create session
    from backend.base.crm.security.models.sessions import Session
    from datetime import datetime, timedelta, timezone
    import secrets

    token = secrets.token_urlsafe(64)
    session = Session(
        user_id=user_id,
        token=token,
        ttl=3600,
        expired_datetime=datetime.now(timezone.utc) + timedelta(hours=1),
        create_user_id=user_id,
        update_user_id=user_id,
        active=True,
    )
    await Session.create(session)

    # Add auth header
    client.headers["Authorization"] = f"Bearer {token}"

    yield client, user_id, token


# ====================
# Factory fixtures
# ====================


@pytest_asyncio.fixture
async def user_factory(db_pool):
    """Factory for creating test users."""
    from backend.base.crm.users.models.users import User
    from backend.base.crm.languages.models.language import Language

    created_ids = []
    lang_id = None

    async def create_user(
        name: str = "Test User",
        login: str = None,
        email: str = None,
        is_admin: bool = False,
        **kwargs,
    ) -> User:
        nonlocal lang_id

        # Create language if needed
        if lang_id is None:
            lang_id = await Language.create(
                Language(
                    code="en",
                    name="English",
                    active=True,
                )
            )

        if login is None:
            login = f"user_{len(created_ids) + 1}"
        if email is None:
            email = f"{login}@test.com"

        user = User(
            name=name,
            login=login,
            password_hash="hash",
            password_salt="salt",
            is_admin=is_admin,
            lang_id=lang_id,
            **kwargs,
        )
        user_id = await User.create(user)
        created_ids.append(user_id)

        return await User.get(user_id)

    yield create_user


@pytest_asyncio.fixture
async def partner_factory(db_pool):
    """Factory for creating test partners."""
    from backend.base.crm.partners.models.partners import Partner

    created_ids = []

    async def create_partner(
        name: str = "Test Partner",
        email: str = None,
        phone: str = None,
        is_customer: bool = True,
        is_supplier: bool = False,
        **kwargs,
    ) -> Partner:
        if email is None:
            email = f"partner_{len(created_ids) + 1}@test.com"

        partner = Partner(
            name=name,
            email=email,
            phone=phone,
            is_customer=is_customer,
            is_supplier=is_supplier,
            **kwargs,
        )
        partner_id = await Partner.create(partner)
        created_ids.append(partner_id)

        return await Partner.get(partner_id)

    yield create_partner


@pytest_asyncio.fixture
async def product_factory(db_pool):
    """Factory for creating test products."""
    from backend.base.crm.products.models.product import Product

    created_ids = []

    async def create_product(
        name: str = "Test Product",
        price: float = 100.0,
        active: bool = True,
        **kwargs,
    ) -> Product:
        product = Product(name=name, list_price=price, active=active, **kwargs)
        product_id = await Product.create(product)
        created_ids.append(product_id)

        return await Product.get(product_id)

    yield create_product


@pytest_asyncio.fixture
async def lead_factory(db_pool, partner_factory):
    """Factory for creating test leads."""
    from backend.base.crm.leads.models.leads import Lead
    from backend.base.crm.leads.models.lead_stage import LeadStage

    created_ids = []
    stage_id = None

    async def create_lead(
        name: str = "Test Lead", partner: "Partner" = None, **kwargs
    ) -> Lead:
        nonlocal stage_id

        # Create stage if needed
        if stage_id is None:
            stage_id = await LeadStage.create(
                LeadStage(
                    name="New",
                    sequence=1,
                )
            )

        # Create partner if not provided
        if partner is None:
            partner = await partner_factory()

        lead = Lead(
            name=name, partner_id=partner.id, stage_id=stage_id, **kwargs
        )
        lead_id = await Lead.create(lead)
        created_ids.append(lead_id)

        return await Lead.get(lead_id)

    yield create_lead


@pytest_asyncio.fixture
async def sale_factory(db_pool, partner_factory):
    """Factory for creating test sales."""
    from backend.base.crm.sales.models.sale import Sale
    from backend.base.crm.sales.models.sale_stage import SaleStage

    created_ids = []
    stage_id = None

    async def create_sale(
        name: str = None, partner: "Partner" = None, **kwargs
    ) -> Sale:
        nonlocal stage_id

        # Create stage if needed
        if stage_id is None:
            stage_id = await SaleStage.create(
                SaleStage(
                    name="Draft",
                    sequence=1,
                )
            )

        # Create partner if not provided
        if partner is None:
            partner = await partner_factory()

        if name is None:
            name = f"SO-{len(created_ids) + 1:04d}"

        sale = Sale(
            name=name, partner_id=partner.id, stage_id=stage_id, **kwargs
        )
        sale_id = await Sale.create(sale)
        created_ids.append(sale_id)

        return await Sale.get(sale_id)

    yield create_sale


# ====================
# Utility fixtures
# ====================


@pytest.fixture
def mock_env():
    """Create mock environment for unit tests."""
    env = MagicMock()
    env.models = MagicMock()
    env.apps = MagicMock()
    env.apps.db = MagicMock()
    env.apps.db.get_session = MagicMock(return_value=AsyncMock())
    env.apps.db.get_transaction = MagicMock()
    return env


@pytest.fixture
def sample_user_data():
    """Sample user data for tests."""
    return {
        "name": "John Doe",
        "login": "johndoe",
        "email": "john@example.com",
        "password": "SecurePassword123!",
    }


@pytest.fixture
def sample_partner_data():
    """Sample partner data for tests."""
    return {
        "name": "Acme Corp",
        "email": "contact@acme.com",
        "phone": "+1234567890",
        "is_customer": True,
        "is_supplier": False,
    }


@pytest.fixture
def sample_product_data():
    """Sample product data for tests."""
    return {
        "name": "Widget Pro",
        "list_price": 299.99,
        "active": True,
        "description": "Professional grade widget",
    }
