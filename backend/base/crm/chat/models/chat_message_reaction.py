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

    # Составной индекс для toggle-логики реакций:
    # фильтр (message_id, user_id, emoji) при каждом клике на эмодзи.
    # Также покрывает выборку реакций по message_id (prefix scan).
    __indexes__ = [("message_id", "user_id")]

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
        # FK на users без индекса = seq scan при удалении пользователя
        index=True,
    )

    # Временная метка
    create_datetime: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc), description="Дата создания"
    )

    @classmethod
    async def grouped(cls, message_ids: list[int]) -> dict[int, list[dict]]:
        """Реакции сообщений, сгруппированные по эмодзи:
        message_id → [{"emoji", "users", "count"}]. Одним запросом на все
        сообщения."""
        reactions = await cls.search(
            filter=[("message_id", "in", message_ids)],
            fields=["id", "emoji", "message_id", "user_id"],
        )
        users: dict[int, dict[str, list]] = {}
        for reaction in reactions:
            users.setdefault(reaction.message_id.id, {}).setdefault(
                reaction.emoji, []
            ).append(
                {
                    "user_id": reaction.user_id.id,
                    "user_name": reaction.user_id.name,
                }
            )
        return {
            message_id: [
                {"emoji": emoji, "users": people, "count": len(people)}
                for emoji, people in by_emoji.items()
            ]
            for message_id, by_emoji in users.items()
        }
