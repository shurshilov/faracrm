"""
Integration tests: creating a connector auto-creates its outbox account.

Guards the regression where ``ChatConnector.create`` — a ``@hybridmethod``
invoked from the CLASS by the CRUD router (``Model.create(payload)``) — ran
``_ensure_outbox_account`` against an EMPTY ``self``. So on CREATE neither the
``chat_external_account`` outbox row nor ``connector.outbox_account_id`` was
ever produced (only a later UPDATE, whose ``self`` is the loaded record, fixed
it); the sidebar folder was likewise seeded with ``name=None``. The fix drives
the post-create logic from ``payload``.

The tests call ``ChatConnector.create(payload)`` directly — byte-for-byte the
phase-1 call the CRUD router makes (``id = await Model.create(model_instance)``)
— so they exercise the real regression path, not an instance-level shortcut.

Run: pytest tests/integration/chat/test_connector_outbox.py -v -m integration
"""

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.crm.chat.models.chat_external_account import (
    ChatExternalAccount,
)
from backend.base.crm.chat.models.chat_folder import ChatFolder
from backend.base.system.dotorm_databases_postgres.app import (
    DotormDatabasesPostgresService,
)


@pytest_asyncio.fixture
async def wired_env(app, db_pool):
    """Point the module-global DB-transaction pool at the test database — the
    same wiring test_incoming_pipeline.py relies on. Connector.create reaches
    ``env`` (the module-global one) for chat_external_account / chat_folder, so
    bind the Postgres service pool at the class level to the test pool."""
    DotormDatabasesPostgresService().set_pool(db_pool)
    return app.state.env


async def _make_vk_connector(**overrides) -> int:
    """Create a VK connector via the CLASS-level create() — exactly the path the
    CRUD router uses (Model.create(payload)); returns the new connector id."""
    payload = ChatConnector(
        name="VK-test",
        type="vk",
        lead_distribution=False,
        **overrides,
    )
    return await ChatConnector.create(payload)


async def _linked_outbox_id(connector_id: int):
    """The connector's outbox_account_id, normalized to a plain id (M2O may come
    back as a scalar or a nested object)."""
    rows = await ChatConnector.search(
        filter=[("id", "=", connector_id)],
        fields=["id", "outbox_account_id"],
        limit=1,
    )
    linked = rows[0].outbox_account_id
    if not linked:
        return None
    return linked.id if hasattr(linked, "id") else linked


class TestConnectorOutbox:
    """CREATE auto-creates + links the outbox; the empty-self bug is gone."""

    async def test_create_with_external_account_creates_outbox(
        self, wired_env
    ):
        cid = await _make_vk_connector(external_account_id="72818945")

        # Outbox row created for the connector, keyed by external_account_id.
        accounts = await ChatExternalAccount.search(
            filter=[("connector_id", "=", cid)],
            fields=["id", "external_id"],
        )
        assert len(accounts) == 1
        assert accounts[0].external_id == "72818945"

        # ...and linked back on the connector.
        assert await _linked_outbox_id(cid) == accounts[0].id

    async def test_create_without_external_account_no_outbox(self, wired_env):
        # No external_account_id → nothing to key an outbox on → none created.
        cid = await _make_vk_connector()

        accounts = await ChatExternalAccount.search(
            filter=[("connector_id", "=", cid)],
            fields=["id"],
        )
        assert accounts == []
        assert await _linked_outbox_id(cid) is None

    async def test_create_seeds_connector_folder_with_name(self, wired_env):
        """Same empty-self bug also seeded the sidebar folder with name=None."""
        cid = await _make_vk_connector(external_account_id="72818945")

        folders = await ChatFolder.search(
            filter=[("connector_id", "=", cid), ("user_id", "=", None)],
            fields=["id", "name"],
        )
        assert len(folders) == 1
        assert folders[0].name == "VK-test"

    async def test_update_sets_external_account_creates_outbox(
        self, wired_env
    ):
        """Setting external_account_id via UPDATE also creates the outbox (this
        path already worked before the fix — lock it in)."""
        cid = await _make_vk_connector()  # starts without an outbox
        connector = await ChatConnector.get(cid)

        await connector.update(
            ChatConnector(external_account_id="72818945"),
            fields=["external_account_id"],
        )

        accounts = await ChatExternalAccount.search(
            filter=[("connector_id", "=", cid)],
            fields=["external_id"],
        )
        assert len(accounts) == 1
        assert accounts[0].external_id == "72818945"
        assert await _linked_outbox_id(cid) == accounts[0].id

    async def test_ensure_outbox_is_idempotent(self, wired_env):
        """Re-ensuring with the same external_account_id keeps exactly one
        outbox row (idempotent create → no duplicates)."""
        cid = await _make_vk_connector(external_account_id="72818945")
        connector = await ChatConnector.get(cid)

        # Second pass over the same external id must not add a row.
        await connector.update(
            ChatConnector(external_account_id="72818945"),
            fields=["external_account_id"],
        )

        accounts = await ChatExternalAccount.search(
            filter=[("connector_id", "=", cid)],
            fields=["id"],
        )
        assert len(accounts) == 1
