# Copyright 2025 FARA CRM
# Chat Phone Sipuni module - connector mixin

import secrets
from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.system.dotorm.dotorm.decorators import onchange
from backend.base.system.dotorm.dotorm.fields import Selection

if TYPE_CHECKING:
    _Base = ChatConnector
else:
    _Base = object


@extend(ChatConnector)
class ChatConnectorSipuniMixin(_Base):
    """
    Миксин для ChatConnector с поддержкой Sipuni.

    Добавляет тип 'phone_sipuni' и дефолтные значения.
    """

    DEFAULT_CONNECTOR_URL_SIPUNI = "https://sipuni.com/api"

    type: str = Selection(selection_add=[("phone_sipuni", "Sipuni Phone")])

    @onchange("type")
    async def onchange_type_phone_sipuni(self) -> dict:
        """Установить дефолтные значения при выборе типа phone_sipuni."""
        if self.type == "phone_sipuni":
            webhook_hash = secrets.token_hex(32)
            return {
                "connector_url": self.DEFAULT_CONNECTOR_URL_SIPUNI,
                "webhook_hash": webhook_hash,
                "category": "phone",
            }
        return {}
