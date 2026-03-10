# Copyright 2025 FARA CRM
# Chat Web Push module - notification service
#
# Dispatches notifications via notify-connectors after message creation.

import logging
from typing import TYPE_CHECKING

from backend.base.system.core.enviroment import env
from backend.base.crm.chat.strategies import get_strategy

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User

logger = logging.getLogger(__name__)


async def notify_on_new_message(
    chat_id: int,
    message_id: int,
    author_user_id: "User",
    body: str,
    exclude_user_id: int | None = None,
):
    """
    Send notifications about new message via all notify-connectors.

    Called from post_message after message creation and WebSocket dispatch.

    For each chat member:
    1. Find notify-connectors (connector.notify=True)
    2. For each connector find contacts of matching type
    3. Send notification via connector strategy
    """
    try:
        # 1. Find all active notify-connectors
        notify_connectors = await env.models.chat_connector.search(
            filter=[
                ("active", "=", True),
                ("notify", "=", True),
            ],
            fields=[
                "id",
                "name",
                "type",
                "category",
                "contact_type_id",
                "access_token",
                "client_app_id",
            ],
        )

        if not notify_connectors:
            return

        # 2. Find chat members (only user_id, not partners)
        session = env.apps.db.get_session()
        members_query = """
            SELECT cm.user_id
            FROM chat_member cm
            WHERE cm.chat_id = $1
              AND cm.is_active = true
              AND cm.user_id IS NOT NULL
        """
        members = await session.execute(
            members_query, [chat_id], cursor="fetch"
        )
        member_user_ids = [
            m["user_id"] for m in members if m["user_id"] != exclude_user_id
        ]

        if not member_user_ids:
            return

        # 3. Get chat name for notification
        chat = await env.models.chat.get(chat_id, fields=["name"])
        chat_name = chat.name if chat else f"Chat #{chat_id}"

        # 4. For each notify-connector, dispatch
        for connector in notify_connectors:
            if not connector.contact_type_id:
                logger.warning(
                    "[notify] Connector %s has no contact_type_id, skipping",
                    connector.name,
                )
                continue

            ct_id = connector.contact_type_id.id

            # Find contacts of recipients for this connector type
            contacts = await env.models.contact.search(
                filter=[
                    ("user_id", "in", member_user_ids),
                    ("contact_type_id", "=", ct_id),
                    ("active", "=", True),
                ],
                fields=["id", "name", "user_id"],
            )

            if not contacts:
                continue

            recipients = [
                # {"id": c.id, "contact_value": c.name} for c in contacts
                c.name
                for c in contacts
            ]

            try:
                strategy = get_strategy(connector.type)

                await strategy.chat_send_message(
                    connector=connector,
                    user_from=author_user_id,
                    body=f"{body[:150]}",
                    chat_id=str(chat_id),
                    recipients_ids=recipients,
                )

                logger.info(
                    "[notify] Sent %d notifications via %s for message %d",
                    len(recipients),
                    connector.type,
                    message_id,
                )

            except Exception as e:
                logger.error(
                    "[notify] Failed to send via %s: %s",
                    connector.type,
                    e,
                    exc_info=True,
                )

    except Exception as e:
        # Notifications must not break main flow
        logger.error(
            "[notify] Error in notify_on_new_message: %s",
            e,
            exc_info=True,
        )
