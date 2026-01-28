# Copyright 2025 FARA CRM
# Chat Telegram module - connector mixin

import secrets
from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.system.dotorm.dotorm.decorators import onchange
from backend.base.system.dotorm.dotorm.fields import Selection

# поддержка IDE, видны все аттрибуты базового класса
if TYPE_CHECKING:
    _Base = ChatConnector
else:
    _Base = object


@extend(ChatConnector)
class ChatConnectorTelegramMixin(_Base):
    """
    Миксин для ChatConnector с поддержкой Telegram.

    Добавляет:
    - Тип 'telegram' в Selection поле type
    - Метод для генерации defaults при создании

    В IDE: наследует ChatConnector - видны все поля
    В runtime: @extend применяет расширение к ChatConnector
    """

    DEFAULT_CONNECTOR_URL_TELEGRAM = "https://api.telegram.org"

    # Расширяем Selection поле type
    type: str = Selection(selection_add=[("telegram", "Telegram")])

    @onchange("type")
    async def onchange_type_telegram(self) -> dict:
        """
        Устанавливает значения по умолчанию при выборе типа telegram.

        Returns:
            Словарь с connector_url, webhook_url, webhook_hash
        """
        if self.type == "telegram":
            webhook_hash = secrets.token_hex(32)
            webhook_url = f"YOUR_URL/chat/webhook/{webhook_hash}/CONNECTOR_ID"

            return {
                "connector_url": self.DEFAULT_CONNECTOR_URL_TELEGRAM,
                "webhook_url": webhook_url,
                "webhook_hash": webhook_hash,
                "category": "messenger",
            }
        return {}

    @onchange("access_token")
    async def onchange_external_account_id_telegram(self) -> dict:
        if self.type == "telegram" and self.access_token:
            return {"external_account_id": self.access_token.split(":")[0]}
        return {}
