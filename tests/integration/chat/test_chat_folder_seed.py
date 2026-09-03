"""
Integration test: seeding of the built-in (global) chat folders.

Guards the «folders doubled after a fresh start» regression: the seeder
created the folders without an explicit ``user_id``, so ``create()`` filled
it from the model default (the system user of the post_init session). The
folders stopped being global (the read rule is ``user_id IS NULL``) and the
idempotency check, which looked for a global folder, never found them, so
every start of every worker seeded another full set.

Run: pytest tests/integration/chat/test_chat_folder_seed.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration

from backend.base.crm.chat.models.chat_folder import (
    ChatFolder,
    DEFAULT_GLOBAL_FOLDERS,
)

KINDS = sorted(folder.kind for folder in DEFAULT_GLOBAL_FOLDERS)


async def _builtin_rows():
    """Built-in folders (kind IS NOT NULL), oldest first."""
    rows = await ChatFolder.search(
        filter=[("kind", "!=", None)],
        fields=["id", "kind", "user_id"],
    )
    return sorted(rows, key=lambda r: r.id)


async def test_seeds_one_global_folder_per_kind_and_is_idempotent(db_pool):
    await ChatFolder.ensure_global_defaults()
    first = await _builtin_rows()

    assert sorted(r.kind for r in first) == KINDS
    # Global, not owned by the system user of the seeding session.
    assert all(not r.user_id for r in first)

    await ChatFolder.ensure_global_defaults()

    assert [r.id for r in await _builtin_rows()] == [r.id for r in first]
