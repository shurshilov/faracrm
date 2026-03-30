# Copyright 2025 FARA CRM
# Chat Phone MegaFon module - connector mixin

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
class ChatConnectorMegafonMixin(_Base):
    """
    Миксин для ChatConnector с поддержкой MegaFon VATS.

    Добавляет тип 'phone_megafon' и дефолтные значения.

    Настройка полей коннектора:
    - connector_url: https://{domain}/crmapi/v1 (из ЛК МегаФон)
    - access_token: API ключ для X-API-KEY header (исходящие запросы)
    - vpbx_api_key: CRM токен для валидации входящих webhook
    """

    type: str = Selection(selection_add=[("phone_megafon", "MegaFon VATS")])

    @onchange("type")
    async def onchange_type_phone_megafon(self) -> dict:
        """Установить дефолтные значения при выборе типа phone_megafon."""
        if self.type == "phone_megafon":
            webhook_hash = secrets.token_hex(32)
            return {
                "webhook_hash": webhook_hash,
                "category": "phone",
            }
        return {}
