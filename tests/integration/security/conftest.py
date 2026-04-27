"""Local conftest для security-тестов: после TRUNCATE — post_init."""

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def _security_init(clean_all_tables):
    from tests.conftest import _run_post_init_once

    await _run_post_init_once()
    yield
