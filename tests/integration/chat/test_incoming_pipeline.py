"""
Integration tests for the incoming-message pipeline (IncomingMessagePipeline).

Feeds realistic raw payloads for three channel kinds through the REAL strategy
and adapter, then asserts the resulting DB state and the WebSocket push. The
test is BLACK-BOX on the pipeline: it drives IncomingMessagePipeline exactly as
handle_webhook / the email cron do (inside a transaction) and checks outcomes,
so it is agnostic to the pipeline's internals.

Three channel varieties:
  • email    — two cases (with / without attachments). Self-contained: the
               webhook carries attachment bytes inline (attachments_source=
               "content"), so no download is mocked.
  • avito    — carries an item (объявление): item title becomes the lead name,
               item url becomes the lead website. Avito's chat/item API
               (resolve_partner_id_and_name, get_item_info) is mocked.
  • telegram — a plain messenger with a photo: the file download is mocked to
               return canned bytes ("as if we fetched the file").

Run: pytest tests/integration/chat/test_incoming_pipeline.py -v -m integration
"""

import json
import tempfile
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.crm.chat.models.chat_message import ChatMessage
from backend.base.crm.chat.models.chat_external_chat import ChatExternalChat
from backend.base.crm.chat.models.chat_external_message import (
    ChatExternalMessage,
)
from backend.base.crm.leads.models.leads import Lead
from backend.base.crm.partners.models.contact_type import ContactType
from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.crm.attachments.models.attachments_storage import (
    AttachmentStorage,
)
from backend.base.crm.attachments.models.attachments_route import (
    AttachmentRoute,
)

from backend.base.crm.chat.strategies.pipeline_incoming import (
    IncomingMessagePipeline,
)
from backend.base.crm.chat_email.strategies.strategy import EmailStrategy
from backend.base.crm.chat_avito.strategies.strategy import AvitoStrategy
from backend.base.crm.chat_telegram.strategies.strategy import TelegramStrategy
from backend.base.system.dotorm_databases_postgres.app import (
    DotormDatabasesPostgresService,
)


@pytest_asyncio.fixture
async def wired_env(app, db_pool):
    """app.state.env with the DB-transaction pool pointed at the test database.

    Model internals reached from the pipeline — e.g.
    chat.get_or_create_partner_chat — call `env.apps.db.get_transaction()` on
    the *module-global* env, whose Postgres service never gets its pool
    wired in the test harness (only model `_pool` is bound). get_transaction()
    reads the pool by connection name, so bind it at the service-class level to the session test
    pool — every db-service instance then transacts against the test database.
    """
    DotormDatabasesPostgresService().set_pool(db_pool)
    env = app.state.env

    # Persisting attachment *content* needs a storage route. The app fixture
    # doesn't run AttachmentsApp's default-storage seeding, so seed a filestore
    # storage + catch-all route here (files land in a throwaway temp dir).
    await env.models.system_settings.ensure_defaults(
        [
            {
                "key": "attachments.filestore_path",
                "value": {"value": tempfile.mkdtemp(prefix="fara_test_fs_")},
                "description": "test filestore",
                "module": "attachments",
                "is_system": False,
                "cache_ttl": -1,
            }
        ]
    )
    storages = await AttachmentStorage.search(
        filter=[("type", "=", "file")], limit=1
    )
    if storages:
        storage = storages[0]
    else:
        sid = await AttachmentStorage.create(
            AttachmentStorage(
                name="Test File Storage", type="file", active=True
            )
        )
        storage = await AttachmentStorage.get(sid)
    await AttachmentRoute.ensure_default_route_for_storage(storage)

    return env


# ======================================================================
# Test-payload builders (shape mirrors each provider's real webhook)
# ======================================================================


def build_email(
    *, message_id, sender, subject, text, attachments=None
) -> dict:
    """An IMAP-fetched email (the primary email path, via cron_fetch_emails):
    `raw` carries a parsed email.message.Message, so adapter.raw stays
    JSON-serializable ({uid, source}). attachments = [(name, mime, bytes), ...].
    """
    msg = MIMEMultipart()
    msg["Message-ID"] = message_id
    msg["From"] = sender
    msg["To"] = "shop@company.com"
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))
    for name, mime, content in attachments or []:
        maintype, subtype = mime.split("/", 1)
        part = MIMEBase(maintype, subtype)
        part.set_payload(content)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=name)
        msg.attach(part)
    return {"uid": 1, "parsed": msg}


def avito_payload(*, message_id, chat_id, author_id, text, item_id) -> dict:
    return {
        "payload": {
            "value": {
                "id": message_id,
                "chat_id": chat_id,
                "author_id": author_id,
                "user_id": 999,
                "type": "text",
                "chat_type": "u2i",
                "item_id": item_id,
                "created": 1750000000,
                "content": {"text": text},
            }
        }
    }


def telegram_payload(
    *, message_id, from_id, first_name, username, text, with_photo=False
) -> dict:
    message = {
        "message_id": message_id,
        "from": {
            "id": from_id,
            "is_bot": False,
            "first_name": first_name,
            "username": username,
        },
        "chat": {"id": from_id, "type": "private"},
        "date": 1750000000,
        "text": text,
    }
    if with_photo:
        message["photo"] = [
            {"file_id": "PHOTO_SMALL", "file_size": 100},
            {"file_id": "PHOTO_BIG", "file_size": 9000},
        ]
    return {"update_id": 1, "message": message}


# ======================================================================
# Helpers: connector factory + pipeline driver
# ======================================================================


async def _make_connector(
    *,
    ctype: str,
    is_phone_format: bool = False,
    external_account_id: str | None = None,
    lead_generation: bool = True,
) -> ChatConnector:
    """Create a real connector row (FK integrity for external links / lead),
    then return an in-memory connector carrying exactly the fields the pipeline
    reads — so the test does not depend on ORM nested-loading semantics.
    """
    ct_id = await ContactType.create(
        ContactType(
            name=ctype,
            label=ctype.capitalize(),
            is_phone_format=is_phone_format,
            active=True,
        )
    )
    cid = await ChatConnector.create(
        ChatConnector(
            name=f"{ctype}-test",
            type=ctype,
            contact_type_id=ct_id,
            external_account_id=external_account_id,
            lead_generation=lead_generation,
            lead_distribution=False,
        )
    )
    return ChatConnector(
        id=cid,
        name=f"{ctype}-test",
        type=ctype,
        lead_generation=lead_generation,
        lead_distribution=False,
        lead_type="opportunity",
        lead_stage_id=None,
        external_account_id=external_account_id,
        contact_type_id=ContactType(id=ct_id, is_phone_format=is_phone_format),
    )


async def _drive(strategy, connector, raw, env) -> None:
    """Build the provider adapter and run IncomingMessagePipeline directly —
    the same entry point handle_webhook / the email cron use (the cold-start
    route opens its own transaction internally).
    """
    adapter = strategy.create_message_adapter(connector, raw)
    await IncomingMessagePipeline(strategy, env, connector, adapter).run()


def _ws_inner(mock_chat_ws) -> dict:
    """The inner `message` dict of the single send_to_chat WS push."""
    mock_chat_ws.send_to_chat.assert_called_once()
    return mock_chat_ws.send_to_chat.call_args.kwargs["message"]["message"]


# ======================================================================
# Tests
# ======================================================================


class TestIncomingPipeline:
    """Drive IncomingMessagePipeline with real adapters; assert DB + WS."""

    async def test_email_without_attachments(self, wired_env, mock_chat_ws):
        env = wired_env
        connector = await _make_connector(ctype="email")
        strategy = EmailStrategy()

        raw = build_email(
            message_id="<msg-1@client.com>",
            sender="Ivan Client <ivan@client.com>",
            subject="Order #42",
            text="Hello, I would like to buy your product",
        )
        await _drive(strategy, connector, raw, env)

        inner = _ws_inner(mock_chat_ws)

        # Message persisted with email body-format {subject, html}.
        msg = await ChatMessage.get(inner["id"])
        body = json.loads(msg.body)
        assert body["subject"] == "Order #42"
        assert "buy" in body["html"].lower()

        # WS payload carries the channel + feed tags.
        assert inner["connector_type"] == "email"
        assert inner["author"]["type"] == "partner"
        assert inner["partner_id"] is not None
        assert inner["lead_id"] is not None
        assert inner["attachments"] == []

        # External-chat link keyed by the sender address (email chat_id).
        ext = await ChatExternalChat.search(
            filter=[("connector_id", "=", connector.id)],
            fields=["external_id"],
        )
        assert ext and ext[0].external_id == "ivan@client.com"

        # External-message link keyed by Message-Id.
        ext_msg = await ChatExternalMessage.search(
            filter=[("connector_id", "=", connector.id)],
            fields=["external_id", "message_id"],
        )
        assert ext_msg and ext_msg[0].external_id == "<msg-1@client.com>"

        # Lead generated for the new partner.
        leads = await Lead.search(
            filter=[("connector_id", "=", connector.id)],
            fields=["id", "partner_id"],
        )
        assert len(leads) == 1

        # No attachment rows.
        atts = await Attachment.search(
            filter=[
                ("res_model", "=", "chat_message"),
                ("res_id", "=", inner["id"]),
            ],
            fields=["id"],
        )
        assert atts == []

    async def test_email_with_attachments(self, wired_env, mock_chat_ws):
        env = wired_env
        connector = await _make_connector(ctype="email")
        strategy = EmailStrategy()

        pdf_bytes = b"%PDF-1.4 fake invoice bytes"
        png_bytes = b"\x89PNG\r\n fake photo bytes"
        raw = build_email(
            message_id="<msg-2@client.com>",
            sender="Maria <maria@client.com>",
            subject="Invoice attached",
            text="Please find the invoice and a photo attached",
            attachments=[
                ("invoice.pdf", "application/pdf", pdf_bytes),
                ("photo.png", "image/png", png_bytes),
            ],
        )
        await _drive(strategy, connector, raw, env)

        inner = _ws_inner(mock_chat_ws)

        # Both attachments present in the live WS payload (no page reload).
        assert len(inner["attachments"]) == 2

        # And persisted with the original names + exact byte sizes (inline
        # content — no download involved for email).
        atts = await Attachment.search(
            filter=[
                ("res_model", "=", "chat_message"),
                ("res_id", "=", inner["id"]),
            ],
            fields=["id", "name", "size", "mimetype"],
        )
        by_name = {a.name: a for a in atts}
        assert set(by_name) == {"invoice.pdf", "photo.png"}
        assert by_name["invoice.pdf"].size == len(pdf_bytes)
        assert by_name["photo.png"].size == len(png_bytes)

    async def test_avito_with_item_creates_lead_from_item(
        self, wired_env, mock_chat_ws
    ):
        env = wired_env
        connector = await _make_connector(
            ctype="avito", external_account_id="SHOP_ACCOUNT"
        )
        strategy = AvitoStrategy()
        # Avito resolves the client and the item title/url via its chat API —
        # mock both (return canned data as if we called Avito).
        strategy.resolve_partner_id_and_name = AsyncMock(
            return_value=("CLIENT_1", "Ivan Buyer")
        )
        strategy.get_item_info = AsyncMock(
            return_value={
                "title": "iPhone 12 Pro",
                "url": "https://avito.ru/item/1",
            }
        )

        raw = avito_payload(
            message_id="AV_MSG_1",
            chat_id="AV_CHAT_1",
            author_id="CLIENT_1",
            text="Здравствуйте, товар ещё в наличии?",
            item_id="ITEM_1",
        )
        await _drive(strategy, connector, raw, env)

        inner = _ws_inner(mock_chat_ws)

        # Avito stores plain text as the body.
        msg = await ChatMessage.get(inner["id"])
        assert msg.body == "Здравствуйте, товар ещё в наличии?"
        assert inner["connector_type"] == "avito"

        # The item drives lead naming + website.
        leads = await Lead.search(
            filter=[("connector_id", "=", connector.id)],
            fields=["id", "name", "website"],
        )
        assert len(leads) == 1
        assert leads[0].name == "iPhone 12 Pro"
        assert leads[0].website == "https://avito.ru/item/1"

        # External-chat link caches the item, keyed by the avito chat id.
        ext = await ChatExternalChat.search(
            filter=[("connector_id", "=", connector.id)],
            fields=["external_id", "item_title", "item_url"],
        )
        assert ext[0].external_id == "AV_CHAT_1"
        assert ext[0].item_title == "iPhone 12 Pro"
        assert ext[0].item_url == "https://avito.ru/item/1"

    async def test_telegram_with_photo_downloads_attachment(
        self, wired_env, mock_chat_ws
    ):
        env = wired_env
        connector = await _make_connector(ctype="telegram")
        strategy = TelegramStrategy()

        fake_png = b"\x89PNG\r\n telegram downloaded photo bytes"
        # Telegram downloads by file_id via its API — mock the fetch.
        strategy.file_download = AsyncMock(
            return_value=(fake_png, "image/png")
        )

        raw = telegram_payload(
            message_id=100,
            from_id=526725542,
            first_name="Артем",
            username="eurodoo",
            text="Привет, вот фото",
            with_photo=True,
        )
        await _drive(strategy, connector, raw, env)

        inner = _ws_inner(mock_chat_ws)

        msg = await ChatMessage.get(inner["id"])
        assert msg.body == "Привет, вот фото"
        assert inner["connector_type"] == "telegram"

        # The (mocked) download happened and produced exactly one attachment
        # with the canned bytes.
        strategy.file_download.assert_awaited_once()
        assert len(inner["attachments"]) == 1
        atts = await Attachment.search(
            filter=[
                ("res_model", "=", "chat_message"),
                ("res_id", "=", inner["id"]),
            ],
            fields=["id", "size"],
        )
        assert len(atts) == 1
        assert atts[0].size == len(fake_png)

    async def test_second_message_same_sender_reuses_chat(
        self, wired_env, mock_chat_ws
    ):
        """A follow-up from the same address lands in the SAME chat (routed by
        the external-chat link), not a second one."""
        env = wired_env
        connector = await _make_connector(ctype="email")
        strategy = EmailStrategy()

        for i, msg_id in enumerate(("<a@c.com>", "<b@c.com>")):
            raw = build_email(
                message_id=msg_id,
                sender="Repeat <repeat@client.com>",
                subject=f"Message {i}",
                text=f"Body {i}",
            )
            await _drive(strategy, connector, raw, env)

        # Exactly one external-chat link → both messages share one chat.
        ext = await ChatExternalChat.search(
            filter=[("connector_id", "=", connector.id)],
            fields=["id", "chat_id"],
        )
        assert len(ext) == 1
        chat_id = (
            ext[0].chat_id.id
            if hasattr(ext[0].chat_id, "id")
            else ext[0].chat_id
        )
        msgs = await ChatMessage.search(
            filter=[("chat_id", "=", chat_id)],
            fields=["id"],
        )
        assert len(msgs) == 2
