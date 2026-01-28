# Copyright 2025 FARA CRM
# Chat module - message reaction model

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Datetime,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.chat.models.chat_message import ChatMessage


class ChatMessageReaction(DotModel):
    """
    Модель реакции на сообщение чата - аналог реакций в Telegram.

    Поддерживает:
    - Эмодзи реакции
    - Связь с пользователем и сообщением
    """

    __table__ = "chat_message_reaction"

    id: int = Integer(primary_key=True)

    # Эмодзи реакции
    emoji: str = Char(
        max_length=10, description="Эмодзи реакции", required=True
    )

    # Связь с сообщением
    message_id: "ChatMessage" = Many2one(
        relation_table=lambda: env.models.chat_message,
        description="Сообщение, на которое поставлена реакция",
        required=True,
    )

    # Пользователь, поставивший реакцию
    user_id: "User" = Many2one(
        relation_table=lambda: env.models.user,
        description="Пользователь, поставивший реакцию",
        required=True,
    )

    # Временная метка
    create_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc), description="Дата создания"
    )
