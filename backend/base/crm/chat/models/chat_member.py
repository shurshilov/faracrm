# Copyright 2025 FARA CRM
# Chat module - chat member model (many2many link table)

from typing import TYPE_CHECKING
from starlette.status import HTTP_403_FORBIDDEN

from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Integer,
    Many2one,
)
from backend.base.system.core.exceptions.environment import (
    FaraException,
)
from backend.base.system.membership import MemberMixin
from backend.base.crm.users.audit_mixin import AuditMixin

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat import Chat
    from backend.base.crm.users.models.users import User
    from backend.project_setup import ChatConnector


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

    # ============================================================
    # Admin override: позволяет суперюзеру (User.is_admin=True)
    # читать чужие чаты без членства.
    # ============================================================

    @classmethod
    async def get_or_stub_admin(
        cls,
        chat_id: int,
        user_id: int,
        is_admin: bool,
    ) -> tuple["ChatMember", bool]:
        """
        Для **read**-эндпоинтов: вернуть члена чата, но если это
        суперюзер без членства — отдать в памяти стаб (БД не меняется).

        Returns:
            (member, was_stubbed)
            - member: реальная запись из БД либо стаб
            - was_stubbed: True если вернули стаб (юзер админ без членства)

        Raises:
            FaraException: если юзер не член и не админ
        """
        member = await cls.get_membership(chat_id, user_id)
        if member:
            return member, False
        if not is_admin:
            raise FaraException(
                {
                    "content": "ACCESS_DENIED",
                    "status_code": HTTP_403_FORBIDDEN,
                }
            )
        # Стаб для admin — НЕ сохраняется в БД, только для прохода
        # по коду (доступ к last_read_message_id и т.п.)
        stub = cls(
            chat_id=Chat(id=chat_id),
            user_id=User(id=user_id),
            is_admin=True,
            is_active=True,
            last_read_message_id=0,
            can_read=True,
            can_write=True,
            can_invite=True,
            can_pin=True,
            can_delete_others=True,
        )
        return stub, True

    @classmethod
    async def get_or_stub_reader(
        cls,
        chat_id: int,
        user_id: int,
        is_admin: bool,
    ) -> tuple["ChatMember", bool]:
        """Для READ-эндпоинтов с team-доступом.

        - член чата            → его реальная запись (полные права);
        - админ                → полный стаб (как get_or_stub_admin);
        - team-читатель        → read-only стаб (can_write=False): доступ к чату
          на ЧТЕНИЕ выдан правилом (chat.team_id ∈ {{team_ids}}), но писать надо
          вступив. Проверяем через ORM chat.search — правила chat (member/team)
          сами решают: недоступный чат вернёт пусто → 403;
        - иначе                → 403.

        Запись (post/edit/delete) по-прежнему гейтится check_membership /
        check_can_write — team-читатель туда не проходит.
        """
        member = await cls.get_membership(chat_id, user_id)
        if member:
            return member, False
        if is_admin:
            stub = cls(
                chat_id=Chat(id=chat_id),
                user_id=User(id=user_id),
                is_admin=True,
                is_active=True,
                last_read_message_id=0,
                can_read=True,
                can_write=True,
                can_invite=True,
                can_pin=True,
                can_delete_others=True,
            )
            return stub, True

        # ORM применяет правила модели chat (member OR team) для текущей сессии:
        # доступный чат вернётся, недоступный — пусто. Член/админ уже отсечены
        # выше, значит непустой результат = team-доступ (read-only).
        chats = await env.models.chat.search(
            filter=[("id", "=", chat_id)],
            fields=["id"],
            limit=1,
        )
        if chats:
            reader_stub = cls(
                chat_id=Chat(id=chat_id),
                user_id=User(id=user_id),
                is_admin=False,
                is_active=True,
                last_read_message_id=0,
                can_read=True,
                can_write=False,
                can_invite=False,
                can_pin=False,
                can_delete_others=False,
            )
            return reader_stub, True

        raise FaraException(
            {
                "content": "ACCESS_DENIED",
                "status_code": HTTP_403_FORBIDDEN,
            }
        )

    # @classmethod
    # async def ensure_admin_member(
    #     cls,
    #     chat_id: int,
    #     user_id: int,
    #     is_admin: bool,
    # ) -> "ChatMember":
    #     """
    #     Для **write**-эндпоинтов: гарантировать что юзер — реальный
    #     член чата. Если это admin без членства — создать запись в БД.

    #     После этого admin становится полноценным членом (виден другим
    #     участникам, получает realtime-обновления).

    #     Returns:
    #         ChatMember (всегда сохранённая запись)

    #     Raises:
    #         FaraException: если юзер не член и не админ
    #     """
    #     member, was_stub = await cls.get_or_stub_admin(
    #         chat_id, user_id, is_admin
    #     )
    #     if not was_stub:
    #         return member
    #     # admin был стабом — создаём реальную запись
    #     payload = cls(
    #         chat_id=chat_id,
    #         user_id=user_id,
    #         is_admin=True,
    #         is_active=True,
    #         can_read=True,
    #         can_write=True,
    #         can_invite=True,
    #         can_pin=True,
    #         can_delete_others=True,
    #     )
    #     return await cls.create(payload=payload)
