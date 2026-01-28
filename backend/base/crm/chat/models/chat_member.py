# Copyright 2025 FARA CRM
# Chat module - chat member model (many2many link table)

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Boolean,
    Datetime,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from starlette.status import HTTP_403_FORBIDDEN

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.chat.models.chat import Chat
    from backend.base.crm.partners.models.partners import Partner


class ChatMember(DotModel):
    """
    Связующая модель для участников чата (many2many).

    Участник может быть либо пользователем (user_id), либо партнёром (partner_id).
    Каждый участник имеет набор прав в конкретном чате.
    """

    __table__ = "chat_member"

    id: int = Integer(primary_key=True)

    chat_id: "Chat" = Many2one(
        relation_table=lambda: env.models.chat,
        description="Чат",
        index=True,
    )
    user_id: "User" = Many2one(
        relation_table=lambda: env.models.user,
        description="Участник (пользователь)",
        index=True,
    )
    partner_id: "Partner" = Many2one(
        relation_table=lambda: env.models.partner,
        description="Участник (партнёр)",
        index=True,
    )

    is_active: bool = Boolean(default=True, description="Активный участник")
    joined_at: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc),
        description="Дата присоединения",
    )
    left_at: datetime | None = Datetime(description="Дата выхода")

    # === Права участника ===
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
    is_admin: bool = Boolean(
        default=False, description="Администратор чата (все права)"
    )

    # ==================== Instance Methods ====================

    def has_permission(self, permission: str) -> bool:
        """
        Проверить есть ли у участника определённое право.
        Админ имеет все права.
        """
        if self.is_admin:
            return True
        return getattr(self, permission, False)

    def get_permissions(self) -> dict:
        """Получить все права участника как словарь."""
        return {
            "can_read": self.can_read or self.is_admin,
            "can_write": self.can_write or self.is_admin,
            "can_invite": self.can_invite or self.is_admin,
            "can_pin": self.can_pin or self.is_admin,
            "can_delete_others": self.can_delete_others or self.is_admin,
            "is_admin": self.is_admin,
        }

    # ==================== Class Methods ====================

    @classmethod
    async def get_membership(
        cls,
        chat_id: int,
        user_id: int,
    ) -> Optional["ChatMember"]:
        """
        Получить запись о членстве пользователя в чате.

        Returns:
            ChatMember или None если не найден
        """
        members = await env.models.chat_member.search(
            filter=[
                ("chat_id", "=", chat_id),
                ("user_id", "=", user_id),
                ("is_active", "=", True),
            ],
            fields=[
                "id",
                "is_admin",
                "is_active",
                "can_delete_others",
                "can_invite",
                "can_pin",
                "can_read",
                "can_write",
                "joined_at",
                "left_at",
            ],
            limit=1,
        )
        return members[0] if members else None

    @classmethod
    async def check_membership(
        cls,
        chat_id: int,
        user_id: int,
    ) -> "ChatMember":
        """
        Проверить членство и вернуть ChatMember.
        Бросает FaraException если пользователь не участник.

        Returns:
            ChatMember

        Raises:
            FaraException: ACCESS_DENIED если не участник
        """
        member = await cls.get_membership(chat_id, user_id)
        if not member:
            raise FaraException(
                {"content": "ACCESS_DENIED", "status_code": HTTP_403_FORBIDDEN}
            )
        return member

    @classmethod
    async def check_permission(
        cls,
        chat_id: int,
        user_id: int,
        permission: str,
    ) -> "ChatMember":
        """
        Проверить членство и конкретное разрешение.
        Бросает FaraException если нет доступа или права.

        Args:
            chat_id: ID чата
            user_id: ID пользователя
            permission: Имя права (can_read, can_write, can_invite, can_pin,
                       can_delete_others, is_admin)

        Returns:
            ChatMember

        Raises:
            FaraException: ACCESS_DENIED если не участник
            FaraException: PERMISSION_DENIED если нет права
        """
        member = await cls.check_membership(chat_id, user_id)

        if not member.has_permission(permission):
            raise FaraException(
                {
                    "content": "PERMISSION_DENIED",
                    "detail": f"Required permission: {permission}",
                    "status_code": HTTP_403_FORBIDDEN,
                }
            )
        return member

    @classmethod
    async def check_admin(
        cls,
        chat_id: int,
        user_id: int,
    ) -> "ChatMember":
        """
        Проверить что пользователь админ чата.
        Shortcut для check_permission(chat_id, user_id, "is_admin").

        Returns:
            ChatMember

        Raises:
            FaraException: ACCESS_DENIED если не участник
            FaraException: ADMIN_REQUIRED если не админ
        """
        member = await cls.check_membership(chat_id, user_id)

        if not member.is_admin:
            raise FaraException(
                {
                    "content": "ADMIN_REQUIRED",
                    "status_code": HTTP_403_FORBIDDEN,
                }
            )
        return member

    @classmethod
    async def check_can_write(
        cls,
        chat_id: int,
        user_id: int,
    ) -> "ChatMember":
        """
        Проверить что пользователь может писать в чат.
        Shortcut для check_permission(chat_id, user_id, "can_write").
        """
        return await cls.check_permission(chat_id, user_id, "can_write")

    @classmethod
    async def check_can_invite(
        cls,
        chat_id: int,
        user_id: int,
    ) -> "ChatMember":
        """
        Проверить что пользователь может приглашать участников.
        Shortcut для check_permission(chat_id, user_id, "can_invite").
        """
        return await cls.check_permission(chat_id, user_id, "can_invite")

    @classmethod
    async def check_can_pin(
        cls,
        chat_id: int,
        user_id: int,
    ) -> "ChatMember":
        """
        Проверить что пользователь может закреплять сообщения.
        Shortcut для check_permission(chat_id, user_id, "can_pin").
        """
        return await cls.check_permission(chat_id, user_id, "can_pin")

    @classmethod
    async def check_can_delete_others(
        cls,
        chat_id: int,
        user_id: int,
    ) -> "ChatMember":
        """
        Проверить что пользователь может удалять чужие сообщения.
        Shortcut для check_permission(chat_id, user_id, "can_delete_others").
        """
        return await cls.check_permission(
            chat_id, user_id, "can_delete_others"
        )
