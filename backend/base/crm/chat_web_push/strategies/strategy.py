# Copyright 2025 FARA CRM
# Chat module - Web Push strategy

from typing import TYPE_CHECKING
import json
import logging

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
from backend.base.crm.chat_web_push.strategies.adapter import (
    WebPushMessageAdapter,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class WebPushStrategy(ChatStrategyBase):
    strategy_type = "web_push"

    async def get_or_generate_token(self, connector):
        return connector.access_token

    async def set_webhook(self, connector):
        return True

    async def unset_webhook(self, connector):
        return None

    async def chat_send_message(
        self, connector, user_from, body, chat_id=None, recipients_ids=None
    ):
        import uuid

        message_id = str(uuid.uuid4())
        sent_count = 0
        if not recipients_ids:
            logger.warning("[web_push] No recipients for push notification")
            return message_id, chat_id or ""
        for recipient in recipients_ids:
            # contact_value = recipient.get("contact_value", "")
            contact_value = recipient
            try:
                subscription_info = json.loads(contact_value)
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "[web_push] Invalid subscription JSON for contact %s",
                    recipient.get("id"),
                )
                continue
            success = await self._send_push(
                connector=connector,
                subscription_info=subscription_info,
                title=user_from.name,
                body=body[:200],
                url=f"/chat?id={chat_id}" if chat_id else "/chat",
            )
            if success:
                sent_count += 1
        logger.info(
            "[web_push] Sent %d/%d push notifications",
            sent_count,
            len(recipients_ids),
        )
        return message_id, chat_id or ""

    async def _send_push(
        self, connector, subscription_info, title, body, url="/chat"
    ):
        try:
            from pywebpush import webpush

            vapid_private_key = connector.access_token
            vapid_claims_email = (
                connector.client_app_id or "mailto:admin@fara.com"
            )
            if not vapid_private_key:
                logger.error("[web_push] No VAPID private key in connector")
                return False
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(
                    {
                        "title": title,
                        "body": body,
                        "url": url,
                        "icon": "/icon-192.png",
                        "badge": "/badge-72.png",
                    }
                ),
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": vapid_claims_email},
            )
            return True
        except Exception as e:
            error_msg = str(e)
            if "410" in error_msg:
                logger.info(
                    "[web_push] Subscription expired: %s",
                    subscription_info.get("endpoint", "")[:50],
                )
                return False
            if "404" in error_msg:
                logger.info(
                    "[web_push] Subscription not found: %s",
                    subscription_info.get("endpoint", "")[:50],
                )
                return False
            logger.error("[web_push] Failed to send push: %s", e)
            return False

    def create_message_adapter(self, connector, raw_message):
        return WebPushMessageAdapter(connector, raw_message)
