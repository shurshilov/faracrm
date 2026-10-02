# Copyright 2025 FARA CRM
# Chat module - chat member model (many2many link table)

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Integer,
    Many2one,
)
from backend.base.system.membership import MemberMixin, MemberPermissions
from backend.base.crm.users.audit_mixin import AuditMixin

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat import Chat
    from backend.project_setup import ChatConnector


@dataclass(frozen=True)
class ChatPermissions(MemberPermissions):
    """Права участника чата: общие и свои can_*-поля ChatMember."""

    can_pin: bool = False
    can_delete_others: bool = False


# Обычный участник группы, клиентского чата и заметок записи.
MEMBER = ChatPermissions(can_read=True, can_write=True)
# В личном чате оба могут закреплять сообщения.
DIRECT = ChatPermissions(can_read=True, can_write=True, can_pin=True)
# Создатель группы и первый пользователь клиентского чата.
ADMIN = ChatPermissions(
    can_read=True,
    can_write=True,
    can_invite=True,
    can_remove=True,
    can_pin=True,
    can_delete_others=True,
    is_admin=True,
)


class ChatMember(AuditMixin, MemberMixin):
    """
    Участник чата.
    Общие поля/методы — из MemberMixin.
    """

    __table__ = "chat_member"
    __auto_crud__ = False

    # Составной индекс для основного паттерна проверки membership:
    # get_membership(chat_id, user_id) → фильтр (chat_id, user_id, is_active=True).
    # Порядок (user_id, chat_id, is_active) — по запросу.
    #
    # Второй индекс — под «ленту» партнёра: партнёрский срой строится джойном
    # chat_message → chat_member по (partner_id, is_active), поэтому partner на
    # сообщение НЕ денормализуем (выводится отсюда).
    __indexes__ = [
        ("user_id", "chat_id", "is_active"),
        ("partner_id", "is_active"),
    ]

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
    # default_db: на старой базе колонка появляется сразу с false у всех.
    can_remove: bool = Boolean(
        default=False,
        default_db=True,
        description="Может удалять участников",
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

    # Закрепление чата — per-user состояние (как и watermark). Закреплённые
    # чаты идут сверху списка getChats. У партнёров-участников не используется.
    is_pinned: bool = Boolean(
        default=False, description="Чат закреплён пользователем"
    )

    # Коннектор по умолчанию для отправки в этом чате — per-user (как is_pinned
    # и watermark). null = internal. Подставляется при открытии чата; меняется
    # галочкой «по умолчанию» в свитчере коннекторов. У партнёров не исп-ся.
    default_connector_id: "ChatConnector | None" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        ondelete="set null",
        description="Коннектор по умолчанию (per-user, null=internal)",
    )

    @classmethod
    async def list_for_chats(cls, chat_ids: list[int]) -> dict[int, list]:
        """Участники чатов с именами, аватарами и правами: chat_id → список.

        Форма ответа GET /chats и GET /chats/{id}. Имя и аватар участника —
        пользователя или партнёра — одним запросом; правила доступа к чатам
        уже проверил вызывающий.
        """
        rows = await cls._get_db_session().execute(
            """
            SELECT cm.chat_id,
                   COALESCE(u.id, p.id) AS id,
                   COALESCE(u.name, p.name) AS name,
                   CASE WHEN cm.user_id IS NOT NULL
                        THEN 'user' ELSE 'partner' END AS member_type,
                   COALESCE(u.image, p.image) AS image_id,
                   cm.can_read, cm.can_write, cm.can_invite, cm.can_remove,
                   cm.can_pin, cm.can_delete_others, cm.is_admin
            FROM chat_member cm
            LEFT JOIN users u ON u.id = cm.user_id
            LEFT JOIN partners p ON p.id = cm.partner_id
            WHERE cm.chat_id = ANY(%s) AND cm.is_active = true
            """,
            (chat_ids,),
        )
        members: dict[int, list] = {}
        for row in rows:
            members.setdefault(row["chat_id"], []).append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "member_type": row["member_type"],
                    "image_id": row["image_id"],
                    "permissions": {
                        "can_read": row["can_read"],
                        "can_write": row["can_write"],
                        "can_invite": row["can_invite"],
                        "can_remove": row["can_remove"],
                        "can_pin": row["can_pin"],
                        "can_delete_others": row["can_delete_others"],
                        "is_admin": row["is_admin"],
                    },
                }
            )
        return members

    async def check_not_last_admin(self, chat_id: int) -> None:
        """Последний админ не уходит из чата и не теряет права: сначала
        передаёт их другому участнику."""
        if self.is_admin and await self.count_admins(chat_id) == 1:
            raise FaraException(
                {"content": "CANNOT_REMOVE_THE_LAST_CHAT_ADMIN"}
            )
