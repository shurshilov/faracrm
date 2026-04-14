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
        await self._ensure_rules(env)

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

        pywebpush expects:
        - private key: raw 32 bytes as base64url (no padding)
        - public key: uncompressed EC point as base64url (no padding)

        Returns:
            (private_key_base64url, public_key_base64url)
        """
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        import base64

        private_key = ec.generate_private_key(ec.SECP256R1())

        # Raw 32-byte private scalar → base64url
        raw_private = private_key.private_numbers().private_value.to_bytes(
            32, "big"
        )
        private_b64 = (
            base64.urlsafe_b64encode(raw_private).rstrip(b"=").decode()
        )

        # Uncompressed public point (65 bytes) → base64url
        public_bytes = private_key.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        public_b64 = (
            base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode()
        )

        return private_b64, public_b64

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
            private_b64, public_b64 = ChatWebPushApp._generate_vapid_keys()
            logger.info("[web_push] Generated VAPID key pair")
        except Exception as e:
            logger.error("[web_push] Failed to generate VAPID keys: %s", e)
            private_b64, public_b64 = "", ""

        await env.models.chat_connector.create(
            env.models.chat_connector(
                name="Web Push Notifications",
                type="web_push",
                category="notification",
                active=True,
                notify=True,
                contact_type_id=ct[0] if ct else None,
                client_app_id=public_b64,  # VAPID public key
                access_token=private_b64,  # VAPID private key (raw base64url)
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

    @staticmethod
    async def _ensure_rules(env):
        """
        Создаёт record-level правило: запрещает обычным пользователям
        редактировать и удалять контакты типа web_push.

        Устроено по той же схеме, что и правила в chat/app.py и users/app.py:
        - role_id=None → правило действует для всех не-админов
          (глобальный User.is_admin получает полный байпас в AccessChecker).
        - perm_update=True, perm_delete=True → правило применяется к этим
          операциям; запись проходит, только если попадает под domain.
        - domain [contact_type_id != <web_push_id>] — значит редактировать
          и удалять можно всё, КРОМЕ web_push-контактов.
        - perm_create/perm_read=False → ничего не ограничиваем, чтение
          и создание остаются в ведении ACL и прочих правил.

        Резолвим id типа web_push прямо здесь, т.к. _ensure_contact_type
        уже отработал. Если типа нет — ничего не делаем, чтобы не упасть
        на старте: правило досоздастся при следующем post_init.
        """
        from backend.base.crm.security.models.rules import Rule

        contact_model = await env.models.model.search(
            filter=[("name", "=", "contact")],
            limit=1,
        )
        if not contact_model:
            logger.warning(
                "[web_push] Model 'contact' not found, skip rule creation"
            )
            return

        web_push_type = await env.models.contact_type.search(
            filter=[("name", "=", "web_push")],
            limit=1,
        )
        if not web_push_type:
            logger.warning(
                "[web_push] contact_type 'web_push' not found, skip rule"
            )
            return

        rule_name = "Only admin can edit/delete web_push contacts"
        existing = await env.models.rule.search(
            filter=[("name", "=", rule_name)],
            limit=1,
        )
        if existing:
            return

        await env.models.rule.create(
            payload=Rule(
                name=rule_name,
                active=True,
                model_id=contact_model[0],
                role_id=None,
                domain=[["contact_type_id", "!=", web_push_type[0].id]],
                perm_create=False,
                perm_read=False,
                perm_update=True,
                perm_delete=False,
            ),
        )
