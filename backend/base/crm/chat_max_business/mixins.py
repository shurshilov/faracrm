# Copyright 2025 FARA CRM
# Chat MAX (business) module - connector mixin

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
class ChatConnectorMaxBusinessMixin(_Base):
    """
    Миксин ChatConnector для ОФИЦИАЛЬНОЙ бизнес-интеграции MAX.

    Тип коннектора `max_business` (отдельный от бот-`max` и агрегатора
    `max_wamm`). Это официальный канал «MAX для бизнеса»: верифицированный
    бизнес-аккаунт пишет клиенту первым ПО НОМЕРУ ТЕЛЕФОНА — поэтому тип
    контакта привязываем к `phone`.

    access_token = токен бизнес-аккаунта (выдаётся после регистрации на
    business.max.ru и верификации через Госуслуги/банк). Хост официального
    API — platform-api.max.ru.
    """

    DEFAULT_CONNECTOR_URL_MAX_BUSINESS = "https://platform-api.max.ru"

    # Расширяем Selection поле type
    type: str = Selection(selection_add=[("max_business", "MAX Business")])

    @onchange("type")
    async def onchange_type_max_business(self) -> dict:
        """
        Значения по умолчанию при выборе типа max_business.

        Адресация официального бизнес-канала — по номеру телефона, поэтому
        привязываем тип контакта `phone` (метод сортируется после базового
        onchange_type, его contact_type_id перекрывает базовый —
        см. DotModel.execute_onchange, мёрж по dict.update).
        """
        if self.type == "max_business":
            webhook_hash = secrets.token_hex(32)
            webhook_url = f"YOUR_URL/chat/webhook/{webhook_hash}/CONNECTOR_ID"

            result = {
                "connector_url": self.DEFAULT_CONNECTOR_URL_MAX_BUSINESS,
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
