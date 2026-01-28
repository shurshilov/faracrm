# Copyright 2025 FARA CRM
# Chat WhatsApp ChatApp connector mixin

import secrets
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import onchange
from backend.base.system.dotorm.dotorm.fields import Char, Selection
from backend.base.system.core.extensions import extend
from backend.base.crm.chat.models.chat_connector import ChatConnector

# поддержка IDE, видны все аттрибуты базового класса
if TYPE_CHECKING:
    _Base = ChatConnector
else:
    _Base = object


@extend(ChatConnector)
class ChatConnectorWhatsAppChatAppMixin(_Base):
    """
    Mixin для добавления специфичных полей и методов WhatsApp ChatApp к ChatConnector.

    Добавляет:
    - email: Email аккаунта ChatApp
    - password: Пароль аккаунта
    - license_id: ID лицензии WhatsApp
    - Генерацию webhook URL при создании
    """

    DEFAULT_CONNECTOR_URL_CHATAPP = "https://api.chatapp.online/v1/"

    type: str = Selection(
        selection_add=[("whatsapp_chatapp", "WhatsApp (ChatApp)")]
    )

    # Поля специфичные для WhatsApp ChatApp
    email: str | None = Char(max_length=255, description="Email (ChatApp)")
    password: str | None = Char(
        max_length=255, description="Password (ChatApp)"
    )
    license_id: str | None = Char(
        max_length=255, description="License ID (ChatApp)"
    )

    DEFAULT_CONNECTOR_URL_WHATSAPP_CHATAPP = "https://api.chatapp.online/v1/"

    @onchange("type")
    async def onchange_type_whatsapp_chatapp(self) -> dict:
        """
        Устанавливает значения по умолчанию при выборе типа whatsapp_chatapp.

        Returns:
            Словарь с connector_url, webhook_hash, category
        """
        if self.type == "whatsapp_chatapp":
            webhook_hash = secrets.token_hex(32)
            webhook_url = f"YOUR_URL/chat/webhook/{webhook_hash}/CONNECTOR_ID"

            return {
                "connector_url": self.DEFAULT_CONNECTOR_URL_CHATAPP,
                "webhook_url": webhook_url,
                "webhook_hash": webhook_hash,
                "category": "messenger",
            }
        return {}
