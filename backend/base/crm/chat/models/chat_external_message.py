# Copyright 2025 FARA CRM
# Chat module - external message model

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
    from backend.base.crm.chat.models.chat_message import ChatMessage
    from backend.base.crm.chat.models.chat_connector import ChatConnector


class ChatExternalMessage(DotModel):
    """
    Связь между внутренним сообщением FARA CRM и внешним сообщением.

    Позволяет:
    - Отслеживать какое внутреннее сообщение соответствует какому внешнему
    - Избегать дублирования сообщений при получении вебхуков
    - Связывать отправленные сообщения с их внешними ID
    """

    __table__ = "chat_external_message"

    id: int = Integer(primary_key=True)

    # Внешний идентификатор сообщения
    external_id: str = Char(
        max_length=255,
        required=True,
        description="ID сообщения во внешней системе",
    )

    # ID внешнего чата (для быстрого поиска)
    external_chat_id: str | None = Char(
        max_length=255, description="ID чата во внешней системе"
    )

    # Связь с коннектором
    connector_id: "ChatConnector" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        required=True,
        ondelete="cascade",
        description="Коннектор",
    )

    # Связь с внутренним сообщением
    message_id: "ChatMessage" = Many2one(
        relation_table=lambda: env.models.chat_message,
        required=True,
        ondelete="cascade",
        description="Внутреннее сообщение FARA CRM",
    )

    # Временные метки
    create_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )

    async def find_by_external_id(
        self,
        external_id: str,
        connector_id: int,
        external_chat_id: str | None = None,
    ):
        """
        Найти связь по внешнему ID сообщения.

        Args:
            external_id: Внешний ID сообщения
            connector_id: ID коннектора
            external_chat_id: ID внешнего чата (опционально для уточнения)
        """
        filter_conditions = [
            ("external_id", "=", external_id),
            ("connector_id", "=", connector_id),
        ]

        if external_chat_id:
            filter_conditions.append(
                ("external_chat_id", "=", external_chat_id)
            )

        results = await self.search(filter=filter_conditions, limit=1)

        return results[0] if results else None

    @hybridmethod
    async def exists(self, external_id: str, connector_id: int) -> bool:
        """
        Проверить существует ли сообщение с данным внешним ID.
        Используется для избежания дублей при обработке вебхуков.
        """
        existing = await self.find_by_external_id(external_id, connector_id)
        return existing is not None

    @hybridmethod
    async def create_link(
        self,
        external_id: str,
        connector_id: int,
        message_id: int,
        external_chat_id: str | None = None,
    ):
        """
        Создать связь между внешним и внутренним сообщением.
        """

        link = ChatExternalMessage(
            external_id=external_id,
            external_chat_id=external_chat_id,
            connector_id=env.models.chat_connector(id=connector_id),
            message_id=env.models.chat_message(id=message_id),
        )

        link.id = await self.create(payload=link)
        return link
