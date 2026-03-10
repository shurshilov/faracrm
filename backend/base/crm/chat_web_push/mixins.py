# Copyright 2025 FARA CRM
from typing import TYPE_CHECKING
from backend.base.system.core.extensions import extend
from backend.base.crm.chat.models.chat_connector import ChatConnector
from backend.base.system.dotorm.dotorm.fields import Selection

if TYPE_CHECKING:
    _Base = ChatConnector
else:
    _Base = object


@extend(ChatConnector)
class ChatConnectorWebPushMixin(_Base):
    type: str = Selection(selection_add=[("web_push", "Web Push")])
