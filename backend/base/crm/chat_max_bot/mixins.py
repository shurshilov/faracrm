# Copyright 2025 FARA CRM
# Chat MAX (bot) module - connector mixin

import secrets
from typing import TYPE_CHECKING

from backend.base.system.core.enviroment import env
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
class ChatConnectorMaxBotMixin(_Base):
    """
    Миксин для ChatConnector с поддержкой мессенджера MAX (МАКС).

    Добавляет:
    - Тип 'max' в Selection поле type
    - Метод для генерации defaults при создании

    В IDE: наследует ChatConnector - видны все поля
    В runtime: @extend применяет расширение к ChatConnector

    В отличие от Telegram, токен бота MAX не содержит id бота, поэтому
    external_account_id (user_id бота) не вычисляется из токена — его можно
    получить кнопкой "Получить данные аккаунта" (метод GET /me стратегии).
    """

    DEFAULT_CONNECTOR_URL_MAX_BOT = "https://botapi.max.ru"

    # Расширяем Selection поле type
    type: str = Selection(selection_add=[("max_bot", "MAX (бот)")])

    @onchange("type")
    async def onchange_type_max_bot(self) -> dict:
        """
        Устанавливает значения по умолчанию при выборе типа max.

        Returns:
            Словарь с connector_url, webhook_url, webhook_hash, category
        """
        if self.type == "max_bot":
            webhook_hash = secrets.token_hex(32)
            webhook_url = f"YOUR_URL/chat/webhook/{webhook_hash}/CONNECTOR_ID"

            result = {
                "connector_url": self.DEFAULT_CONNECTOR_URL_MAX_BOT,
                "webhook_url": webhook_url,
                "webhook_hash": webhook_hash,
                "category": "messenger",
            }

            phone_type = await env.models.contact_type.search(
                filter=[("name", "=", "max")],
                fields=["id", "name"],
                limit=1,
            )
            if phone_type:
                result["contact_type_id"] = phone_type[0]
            return result
        return {}
