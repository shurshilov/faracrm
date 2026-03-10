# Copyright 2025 FARA CRM
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.core.app import App

logger = logging.getLogger(__name__)


class ChatWebPushApp(App):
    info = {
        "name": "Chat Web Push",
        "summary": "Web Push notifications for chat module",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat"],
        "post_init": True,
        "sequence": 125,
    }

    def __init__(self):
        super().__init__()
        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_web_push.strategies import WebPushStrategy

        register_strategy(WebPushStrategy)

    async def post_init(self, app: "FastAPI"):
        """Ensure contact_type and seed connector exist after DB is ready."""
        await super().post_init(app)
        env: "Environment" = app.state.env

        await self._ensure_contact_type(env)
        await self._ensure_seed_connector(env)

    @staticmethod
    async def _ensure_contact_type(env):
        existing = await env.models.contact_type.search(
            filter=[("name", "=", "web_push")],
            limit=1,
        )
        if not existing:
            await env.models.contact_type.create(
                env.models.contact_type(
                    name="web_push",
                    display_name="Web Push",
                    icon="device-mobile",
                )
            )
            logger.info("[web_push] Created contact_type web_push")

    @staticmethod
    def _generate_vapid_keys() -> tuple[str, str]:
        """
        Generate VAPID key pair using cryptography library.

        Returns:
            (private_key_pem, public_key_base64url)
        """
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        import base64

        private_key = ec.generate_private_key(ec.SECP256R1())

        private_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

        public_bytes = private_key.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        public_b64 = (
            base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode()
        )

        return private_pem, public_b64

    @staticmethod
    async def _ensure_seed_connector(env):
        existing = await env.models.chat_connector.search(
            filter=[("type", "=", "web_push")],
            limit=1,
        )
        if existing:
            return

        ct = await env.models.contact_type.search(
            filter=[("name", "=", "web_push")],
            limit=1,
        )

        # Auto-generate VAPID keys
        try:
            private_pem, public_b64 = ChatWebPushApp._generate_vapid_keys()
            logger.info("[web_push] Generated VAPID key pair")
        except Exception as e:
            logger.error("[web_push] Failed to generate VAPID keys: %s", e)
            private_pem, public_b64 = "", ""

        await env.models.chat_connector.create(
            env.models.chat_connector(
                name="Web Push Notifications",
                type="web_push",
                category="notification",
                active=True,
                notify=True,
                contact_type_id=ct[0] if ct else None,
                client_app_id=public_b64,  # VAPID public key
                access_token=private_pem,  # VAPID private key
                last_response=(
                    "VAPID keys auto-generated.\n"
                    "To activate: set active = True.\n"
                    "Users will see Push toggle in their profile menu."
                ),
            )
        )
        logger.info(
            "[web_push] Created seed connector (inactive, VAPID keys ready)"
        )
