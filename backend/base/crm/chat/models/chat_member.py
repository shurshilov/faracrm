# Copyright 2025 FARA CRM
# Chat module - chat member model (many2many link table)

from typing import TYPE_CHECKING

from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Integer,
    Many2one,
)
from backend.base.system.membership import MemberMixin

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat import Chat


class ChatMember(MemberMixin):
    """
    Участник чата.
    Общие поля/методы — из MemberMixin.
    """

    __table__ = "chat_member"
    __auto_crud__ = False

    # Составной индекс для основного паттерна проверки membership:
    # get_membership(chat_id, user_id) → фильтр (chat_id, user_id, is_active=True).
    # Порядок (user_id, chat_id, is_active) — по запросу.
    __indexes__ = [("user_id", "chat_id", "is_active")]

    _member_res_field = "chat_id"
    _member_res_model = staticmethod(lambda: env.models.chat)

    id: int = Integer(primary_key=True)

    chat_id: "Chat" = Many2one(
        relation_table=lambda: env.models.chat,
        description="Чат",
        index=True,
    )

    # Права для чат ролей
    can_read: bool = Boolean(
        default=True, description="Может читать сообщения"
    )
    can_write: bool = Boolean(
        default=True, description="Может отправлять сообщения"
    )
    can_invite: bool = Boolean(
        default=False, description="Может приглашать участников"
    )
    can_pin: bool = Boolean(
        default=False, description="Может закреплять сообщения"
    )
    can_delete_others: bool = Boolean(
        default=False, description="Может удалять чужие сообщения"
    )

    last_read_message_id: int | None = Integer(
        description="ID последнего прочитанного сообщения (watermark)",
    )

    # Поскольку роутеры используют эти имена в 15+ местах, сохраняем их
    # как тонкие обёртки над check_permission().
    # TODO: удалить и использовать стандартный метод из миксина
    @classmethod
    async def check_can_write(cls, chat_id: int, user_id: int) -> "ChatMember":
        return await cls.check_permission(chat_id, user_id, "can_write")

    @classmethod
    async def check_can_invite(
        cls, chat_id: int, user_id: int
    ) -> "ChatMember":
        return await cls.check_permission(chat_id, user_id, "can_invite")

    @classmethod
    async def check_can_pin(cls, chat_id: int, user_id: int) -> "ChatMember":
        return await cls.check_permission(chat_id, user_id, "can_pin")

    @classmethod
    async def check_can_delete_others(
        cls, chat_id: int, user_id: int
    ) -> "ChatMember":
        return await cls.check_permission(
            chat_id, user_id, "can_delete_others"
        )
