# Copyright 2025 FARA CRM
# Chat module - external chat model

from datetime import datetime, timezone
from typing import TYPE_CHECKING


from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Datetime,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat import Chat
    from backend.base.crm.chat.models.chat_connector import ChatConnector


class ChatExternalChat(DotModel):
    """
    Связь между внутренним чатом FARA CRM и внешним чатом в стороннем сервисе.

    Позволяет отслеживать какой внутренний чат соответствует какому внешнему.
    Один внутренний чат может иметь несколько внешних связей
    (например, клиент пишет и в Telegram, и в WhatsApp).
    """

    __table__ = "chat_external_chat"

    id: int = Integer(primary_key=True)

    # Внешний идентификатор чата в стороннем сервисе
    external_id: str = Char(
        max_length=255, required=True, description="ID чата во внешней системе"
    )

    # Связь с коннектором
    connector_id: "ChatConnector" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        required=True,
        ondelete="cascade",
        description="Коннектор",
    )

    # Связь с внутренним чатом
    chat_id: "Chat" = Many2one(
        relation_table=lambda: env.models.chat,
        required=True,
        ondelete="cascade",
        description="Внутренний чат FARA CRM",
    )

    # Временные метки
    create_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )

    @hybridmethod
    async def find_by_external_id(self, external_id: str, connector_id: int):
        """
        Найти связь по внешнему ID чата и коннектору.
        """
        results = await self.search(
            filter=[
                ("external_id", "=", external_id),
                ("connector_id", "=", connector_id),
            ],
            fields=["chat_id"],
            limit=1,
        )

        return results[0] if results else None

    @hybridmethod
    async def create_link(
        self, external_id: str, connector_id: int, chat_id: int
    ):
        """
        Создать связь между внешним и внутренним чатом.
        """
        link = ChatExternalChat(
            external_id=external_id,
            connector_id=env.models.chat_connector(id=connector_id),
            chat_id=env.models.chat(id=chat_id),
        )

        link.id = await self.create(payload=link)
        return link
