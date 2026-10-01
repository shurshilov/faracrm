"""Local conftest для тестов отчётов: после TRUNCATE — post_init (роли, ACL,
шаблоны-образцы), как у security-тестов."""

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def _report_init(clean_all_tables):
    from tests.conftest import _run_post_init_once

    await _run_post_init_once()
    yield
