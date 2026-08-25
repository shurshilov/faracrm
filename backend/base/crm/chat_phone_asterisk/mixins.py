# Copyright 2025 FARA CRM
# Chat Phone Asterisk module - connector mixin

from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.crm.chat_phone.connector import phone_connector_defaults
from backend.base.system.dotorm.dotorm.decorators import onchange
from backend.base.system.dotorm.dotorm.fields import Char, Selection

if TYPE_CHECKING:
    _Base = ChatConnector
else:
    _Base = object


@extend(ChatConnector)
class ChatConnectorAsteriskMixin(_Base):
    """
    Миксин для ChatConnector с поддержкой Asterisk / FreePBX.

    Добавляет тип 'phone_asterisk' и дефолтные значения.

    Транспорт — внешний Asterisk-agent (FastAPI рядом с Asterisk):
      * ARI-события агент шлёт на универсальный webhook FARA;
      * историю (CDR), записи и номера FARA тянет из REST API агента по
        HTTP Basic-auth.
    Поля: connector_url, access_token (login), refresh_token (password),
    webhook_url, webhook_hash.
    """

    type: str = Selection(
        selection_add=[("phone_asterisk", "Asterisk / FreePBX")]
    )

    # Звонилка в браузере (SIP поверх WebSocket). Пустой sip_ws_url = выключена:
    # кнопка в шапке не появится. Пароль регистрации — у линии сотрудника
    # (phone_number.sip_password), здесь только общий транспорт.
    sip_ws_url: str = Char(
        max_length=500, description="URL WSS (wss://pbx:8089/ws)"
    )
    sip_realm: str = Char(max_length=255, description="SIP-домен (realm)")
    # ДОПОЛНЕНИЕ к общесистемному релею (TURN__* в .env), а не замена: общий
    # список приходит из /ice/servers и одинаков для звонилки и внутренних
    # звонков. Здесь — только если у конкретной АТС есть свой сервер.
    sip_ice: str = Char(
        max_length=500,
        description="Доп. ICE-серверы этой АТС, через запятую",
    )

    @onchange("type")
    async def onchange_type_phone_asterisk(self) -> dict:
        """Установить дефолтные значения при выборе типа phone_asterisk."""
        if self.type == "phone_asterisk":
            return await phone_connector_defaults()
        return {}
