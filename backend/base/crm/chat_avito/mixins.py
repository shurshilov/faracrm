# Copyright 2025 FARA CRM
# Chat Avito connector mixin

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
class ChatConnectorAvitoMixin(_Base):
    """
    Mixin для добавления специфичных полей и методов Avito к ChatConnector.

    Добавляет:
    - client_secret: секрет приложения Avito
    - Генерацию webhook URL при создании
    - Установку connector_url по умолчанию
    """

    # Расширяем Selection поле type
    type: str = Selection(selection_add=[("avito", "Avito")])

    # Поля специфичные для Avito
    client_secret: str | None = Char(
        max_length=255, description="Client secret (Avito)"
    )

    DEFAULT_CONNECTOR_URL_AVITO = "https://api.avito.ru/messenger/"

    @onchange("type")
    async def onchange_type_avito(self) -> dict:
        """
        Устанавливает значения по умолчанию при выборе типа avito.

        Returns:
            Словарь с connector_url, webhook_hash, category
        """
        if self.type == "avito":
            webhook_hash = secrets.token_hex(32)
            webhook_url = f"YOUR_URL/chat/webhook/{webhook_hash}/CONNECTOR_ID"

            return {
                "connector_url": self.DEFAULT_CONNECTOR_URL_AVITO,
                "webhook_url": webhook_url,
                "webhook_hash": webhook_hash,
                "category": "messenger",
            }
        return {}
