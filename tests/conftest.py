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

# Prefix для auto_crud роутов. Используй auto() для формирования URL.
# Пример: auto("/users/search") → "/auto/users/search"
AUTO_CRUD_PREFIX = "/auto"


def auto(path: str) -> str:
    """Добавляет prefix auto_crud к пути. auto("/users/1") → "/auto/users/1" """
    return f"{AUTO_CRUD_PREFIX}{path}"


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
_apps_instance = None

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
            print(f"\n[OK] Created test database: {TEST_DB_NAME}")
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
        print(f"\n[OK] Dropped test database: {TEST_DB_NAME}")
    finally:
        await conn.close()


# ====================
# Session-scoped fixtures
# ====================


@pytest.fixture(scope="session", autouse=True)
async def manage_test_database():
    """Create test database at session start, drop at end.

    DIAGNOSTIC: drop отключён — БД остаётся для проверки руками.
    """
    if asyncpg is None:
        pytest.skip("asyncpg not installed")
        return

    await _ensure_database()
    yield
    # await _drop_database()  # отключено для диагностики


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
# Module state — _apps_instance кэшируется чтобы не пересоздавать каждый раз


async def _run_post_init_once():
    """Однократная инициализация: post_init всех apps. Session-scoped."""
    from types import SimpleNamespace

    global _apps_instance

    from backend.base.system.core.enviroment import env
    import backend.project_setup  # noqa: F401

    if _apps_instance is None:
        _apps_instance = env.apps

    fake_app = SimpleNamespace(state=SimpleNamespace(env=env))

    # Два прохода — для разрешения cross-app зависимостей
    for pass_num in range(2):
        for app_obj in _apps_instance.get_list():
            if app_obj.info.get("post_init"):
                try:
                    await app_obj.post_init(fake_app)
                except Exception as e:
                    if pass_num == 0:
                        continue
                    print(
                        f"\n⚠ post_init {app_obj.info.get('name')}: "
                        f"{type(e).__name__}: {e}"
                    )


@pytest_asyncio.fixture(scope="session")
async def initialize_seed_data(db_pool):
    """
    Однократная инициализация seed-данных (роли, ACL, rules).
    НЕ autouse — ломает старые тесты которые не рассчитаны на security.
    Подключается ЯВНО только в security тестах через локальный conftest.
    """
    # Базовый seed
    from backend.base.crm.languages.models.language import Language
    from backend.base.crm.users.models.users import User

    existing_lang = await Language.search(
        filter=[("code", "=", "en")], limit=1
    )
    if not existing_lang:
        await Language.create(
            payload=Language(code="en", name="English", flag="us", active=True)
        )

    existing_admin = await User.search(filter=[("id", "=", 1)], limit=1)
    if not existing_admin:
        await User.create(
            payload=User(
                name="Administrator",
                login="admin",
                is_admin=True,
                password_hash="",
                password_salt="",
            )
        )

    existing_system = await User.search(filter=[("id", "=", 2)], limit=1)
    if not existing_system:
        await User.create(
            payload=User(
                name="System",
                login="system",
                is_admin=True,
                password_hash="",
                password_salt="",
            )
        )

    await _run_post_init_once()
    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_all_tables(db_pool):
    """
    Очищает все таблицы и создаёт минимальный seed (admin/system/lang).
    БЕЗ post_init — старые тесты не рассчитаны на rules/ACL.
    Security-тесты подключают post_init через локальный conftest.
    """
    if _models_instance is not None:
        tables = [m.__table__ for m in _models_instance._get_models()]

        # Дополнительно явно включаем m2m-таблицы и security-таблицы —
        # на случай если какие-то из них не возвращаются _get_models()
        # (наблюдалось: после security-тестов roles/rules/acl остаются
        # в БД хотя должны быть в tables).
        extra_tables = [
            "rules",
            "access_list",
            "role_based_many2many",
            "user_role_many2many",
            "roles",
        ]
        all_tables_set = set(tables) | set(extra_tables)

        if all_tables_set:
            tables_str = ", ".join(all_tables_set)
            try:
                async with db_pool.acquire() as conn:
                    # До TRUNCATE
                    rules_before = 0
                    acl_before = 0
                    try:
                        rules_before = (
                            await conn.fetchval("SELECT COUNT(*) FROM rules")
                            or 0
                        )
                        acl_before = (
                            await conn.fetchval(
                                "SELECT COUNT(*) FROM access_list"
                            )
                            or 0
                        )
                    except Exception:
                        pass

                    await conn.execute(
                        f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE"
                    )

                    # После TRUNCATE
                    rules_after = 0
                    acl_after = 0
                    try:
                        rules_after = (
                            await conn.fetchval("SELECT COUNT(*) FROM rules")
                            or 0
                        )
                        acl_after = (
                            await conn.fetchval(
                                "SELECT COUNT(*) FROM access_list"
                            )
                            or 0
                        )
                    except Exception:
                        pass

                    import sys

                    sys.stderr.write(
                        f"\n>>> CLEAN: rules {rules_before}->{rules_after}, "
                        f"acl {acl_before}->{acl_after}\n"
                    )
                    sys.stderr.flush()
            except Exception as e:
                import sys

                sys.stderr.write(
                    f"\n!!! TRUNCATE FAILED: {type(e).__name__}: {e}\n"
                )
                sys.stderr.flush()

        # Базовый seed: язык + admin + system. Без post_init.
        from backend.base.crm.languages.models.language import Language
        from backend.base.crm.users.models.users import User

        existing_lang = await Language.search(
            filter=[("code", "=", "en")], limit=1
        )
        if not existing_lang:
            await Language.create(
                payload=Language(
                    code="en",
                    name="English",
                    flag="us",
                    active=True,
                )
            )

        existing_admin = await User.search(filter=[("id", "=", 1)], limit=1)
        if not existing_admin:
            await User.create(
                payload=User(
                    name="Administrator",
                    login="admin",
                    is_admin=True,
                    password_hash="",
                    password_salt="",
                )
            )

        existing_system = await User.search(filter=[("id", "=", 2)], limit=1)
        if not existing_system:
            await User.create(
                payload=User(
                    name="System",
                    login="system",
                    is_admin=True,
                    password_hash="",
                    password_salt="",
                )
            )

        # Чистим in-memory кэши
        try:
            from backend.base.crm.security.rule_operators import (
                clear_cache as clear_rules_cache,
            )

            clear_rules_cache()
        except ImportError:
            pass

        try:
            from backend.base.system.core.system_settings import SystemSettings

            if hasattr(SystemSettings, "_cache"):
                SystemSettings._cache.clear()
        except ImportError:
            pass

        # КРИТИЧНО: сбрасываем глобальный access_checker.
        # SecurityApp.post_init выполняет set_access_checker(SecurityAccessChecker)
        # который остаётся в module-level state НАВСЕГДА. Если security-тест
        # запускается раньше старого теста — старый тест начинает проверять
        # ACL/rules и падает с "No read access".
        # Возвращаем базовый AccessChecker который разрешает всё.
        try:
            from backend.base.system.dotorm.dotorm.access import (
                AccessChecker,
                set_access_checker,
            )

            set_access_checker(AccessChecker())
        except ImportError:
            pass


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
        print(f"\n[OK] Created {len(all_models)} tables")


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
    cookie_token = secrets.token_urlsafe(64)
    session = Session(
        user_id=user_id,
        token=token,
        cookie_token=cookie_token,
        ttl=3600,
        expired_datetime=datetime.now(timezone.utc) + timedelta(hours=1),
        create_user_id=user_id,
        update_user_id=user_id,
        active=True,
    )
    await Session.create(session)

    # Add auth header + HttpOnly cookie
    client.headers["Authorization"] = f"Bearer {token}"
    client.cookies.set("session_cookie", cookie_token)

    yield client, user_id, token


# ====================
# Chat WebSocket mocking
# ====================


@pytest_asyncio.fixture
async def mock_chat_ws(test_env):
    """
    Mock chat_manager WebSocket broadcast methods.

    После рефакторинга chat_manager живёт на экземпляре ChatApp
    (test_env.apps.chat.chat_manager), а не как модульный синглтон.
    Эта фикстура патчит send_to_chat / send_to_user / send_to_user_in_chat
    на реальном инстансе, чтобы тесты не уходили в PubSub.

    Использование:
        async def test_something(self, authenticated_client, mock_chat_ws):
            ...
            mock_chat_ws.send_to_chat.assert_called_once()
    """
    from unittest.mock import AsyncMock

    chat_manager = test_env.apps.chat.chat_manager

    originals = {}
    for method_name in (
        "send_to_chat",
        "send_to_user",
        "send_to_user_in_chat",
    ):
        if hasattr(chat_manager, method_name):
            originals[method_name] = getattr(chat_manager, method_name)
            setattr(chat_manager, method_name, AsyncMock())

    yield chat_manager

    # Restore originals
    for method_name, original in originals.items():
        setattr(chat_manager, method_name, original)


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

        # M2M поля (role_ids и т.п.) НЕ сохраняются через create() —
        # обрабатываем их отдельно через update() после создания.
        # См. dotorm/orm/mixins/primary.py:create — only_store=True пропускает m2m.
        m2m_kwargs = {}
        for field_name in list(kwargs.keys()):
            value = kwargs[field_name]
            if isinstance(value, dict) and (
                "selected" in value
                or "created" in value
                or "deleted" in value
                or "unselected" in value
            ):
                # m2m link/unlink требует int id (а не объекты).
                # Конвертируем объекты с .id в int.
                normalized = {}
                for op_key, items in value.items():
                    if isinstance(items, list):
                        normalized[op_key] = [
                            item.id if hasattr(item, "id") else item
                            for item in items
                        ]
                    else:
                        normalized[op_key] = items
                m2m_kwargs[field_name] = normalized
                kwargs.pop(field_name)

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

        # Применяем m2m отдельным update'ом
        if m2m_kwargs:
            created_user = await User.get(user_id)
            await created_user.update(payload=User(**m2m_kwargs))

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
