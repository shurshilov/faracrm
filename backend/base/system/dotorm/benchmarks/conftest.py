"""Benchmark fixtures and configuration."""

import asyncio
import pytest
from typing import AsyncGenerator

# Try to import database drivers
try:
    import asyncpg
except ImportError:
    asyncpg = None

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
except ImportError:
    create_async_engine = None

try:
    from tortoise import Tortoise
except ImportError:
    Tortoise = None


# Database configuration
DATABASE_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "postgres",
    "database": "benchmark_test",
}

DATABASE_URL = (
    f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}"
    f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def dotorm_pool():
    """Create DotORM connection pool."""
    if asyncpg is None:
        pytest.skip("asyncpg not installed")
    
    from dotorm.databases.postgres import ContainerPostgres
    from dotorm.databases.abstract import PostgresPoolSettings, ContainerSettings
    
    pool_settings = PostgresPoolSettings(**DATABASE_CONFIG)
    container_settings = ContainerSettings(driver="asyncpg", reconnect_timeout=10)
    
    container = ContainerPostgres(pool_settings, container_settings)
    pool = await container.create_pool()
    
    yield pool
    
    await container.close_pool()


@pytest.fixture(scope="session")
async def sqlalchemy_engine():
    """Create SQLAlchemy async engine."""
    if create_async_engine is None:
        pytest.skip("SQLAlchemy not installed")
    
    engine = create_async_engine(
        f"postgresql+asyncpg://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}"
        f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}",
        echo=False,
    )
    
    yield engine
    
    await engine.dispose()


@pytest.fixture(scope="session")
async def tortoise_connection():
    """Initialize Tortoise ORM."""
    if Tortoise is None:
        pytest.skip("Tortoise ORM not installed")
    
    await Tortoise.init(
        db_url=f"postgres://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}"
               f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}",
        modules={"models": ["benchmarks.tortoise_models"]},
    )
    
    yield
    
    await Tortoise.close_connections()


@pytest.fixture
async def clean_tables(dotorm_pool):
    """Clean test tables before each test."""
    async with dotorm_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE benchmark_users RESTART IDENTITY CASCADE")
        await conn.execute("TRUNCATE TABLE benchmark_roles RESTART IDENTITY CASCADE")
    yield


def generate_user_data(count: int) -> list[dict]:
    """Generate test user data."""
    return [
        {
            "name": f"User {i}",
            "email": f"user{i}@benchmark.test",
            "active": i % 2 == 0,
        }
        for i in range(count)
    ]


def generate_role_data(count: int) -> list[dict]:
    """Generate test role data."""
    return [
        {
            "name": f"Role {i}",
            "description": f"Description for role {i}",
        }
        for i in range(count)
    ]
