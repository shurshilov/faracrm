# Copyright 2025 FARA CRM
# Generic polymorphic membership mixin.

from dataclasses import asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, ClassVar, NoReturn, Self

from starlette.status import HTTP_403_FORBIDDEN

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.access import get_access_session
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Datetime,
    Many2one,
)
from ..dotorm.dotorm.model import DotModel
from .permissions import MemberPermissions

if TYPE_CHECKING:
    from backend.base.crm.partners.models.partners import Partner
    from backend.base.crm.users.models.users import User


class MemberMixin(DotModel):
    """
    Миксин для моделей-мемберов полиморфного membership.

    Предоставляет:
      • общие поля: user_id, partner_id, is_active, is_admin, joined_at, left_at
      • состав: add / remove / active_user_ids / count_admins
      • методы членства: get_membership / check_membership
      • права: check_permissions — единая проверка (системный админ, админ
        контейнера, право участника)

    Модель-наследник ДОЛЖЕН объявить:
      __table__ — имя таблицы (например "chat_member")
      _member_res_field — имя FK колонки на контейнер (например "chat_id")
      _member_res_model — lazy-геттер модели-контейнера
                         (обычно: `lambda: env.models.chat`)

    Модель-наследник МОЖЕТ объявить:
      id — если нужен кастомный primary key (иначе возьми Integer(primary_key=True))
      FK на контейнер — отдельным Many2one (миксин НЕ создаёт его сам,
                        потому что у каждой модели своё имя колонки)
      can_* поля — обычные Boolean-колонки; нужные права передают набором:
                   ChatMember.check_permissions(
                       member, ChatPermissions(can_pin=True)
                   )
      свои специфичные поля: last_read_message_id, muted, hourly_rate, ...

    Пример:
        class ChatMember(MemberMixin, DotModel):
            __table__ = "chat_member"
            __auto_crud__ = False

            _member_res_field = "chat_id"
            _member_res_model = staticmethod(lambda: env.models.chat)

            id: int = Integer(primary_key=True)
            chat_id: "Chat" = Many2one(
                relation_table=lambda: env.models.chat,
                index=True,
            )

            # свои права:
            can_read = Boolean(default=True)
            can_write = Boolean(default=True)
            can_pin = Boolean(default=False)

            # специфичное:
            last_read_message_id = Integer()
    """

    # Имя FK-колонки на контейнер: 'chat_id', 'project_id', etc.
    _member_res_field: ClassVar[str]

    # Lazy-геттер модели-контейнера: lambda: env.models.chat
    _member_res_model: ClassVar

    # общие поля
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
    is_admin: bool = Boolean(
        default=False,
        description="Администратор (все права в контексте контейнера)",
    )

    joined_at: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc),
        description="Дата присоединения",
    )
    left_at: datetime | None = Datetime(description="Дата выхода")

    @classmethod
    async def add(
        cls,
        container_id: int,
        permissions: MemberPermissions,
        *,
        user_id: int | None = None,
        partner_id: int | None = None,
    ) -> int:
        """Добавить участника — пользователя или партнёра — с правами."""
        member = cls(
            **{
                cls._member_res_field: cls._member_res_model()(id=container_id)
            },
            **asdict(permissions),
        )
        if user_id:
            member.user_id = env.models.user(id=user_id)
        if partner_id:
            member.partner_id = env.models.partner(id=partner_id)
        return await cls.create(payload=member)

    @classmethod
    async def remove(cls, container_id: int, user_id: int) -> bool:
        """Убрать пользователя из участников (мягко: is_active=False).
        False — участником он не был."""
        member = await cls.get_membership(container_id, user_id, fields=["id"])
        if not member:
            return False
        await member.update(
            cls(is_active=False, left_at=datetime.now(timezone.utc))
        )
        return True

    @classmethod
    async def active_user_ids(cls, container_id: int) -> list[int]:
        """Пользователи-участники контейнера (у чата — адресаты WS-событий).

        Сырой SQL через _get_db_session(): внутри транзакции это ЕЁ соединение,
        поэтому участник, добавленный в этой же транзакции, в список попадёт.
        И без правил доступа — состав не должен зависеть от того, что видит
        текущий пользователь. Партнёров не берём.
        """
        rows = await cls._get_db_session().execute(
            f"SELECT user_id FROM {cls.__table__} "
            f"WHERE {cls._member_res_field} = %s "
            "AND user_id IS NOT NULL AND is_active = true",
            (container_id,),
        )
        return [row["user_id"] for row in rows]

    @classmethod
    async def count_admins(cls, container_id: int) -> int:
        """Сколько у контейнера админов. sudo: вступающий участников ещё
        не видит."""
        return await cls.sudo().search_count(
            filter=[
                (cls._member_res_field, "=", container_id),
                ("is_admin", "=", True),
                ("is_active", "=", True),
            ]
        )

    @classmethod
    async def get_membership(
        cls,
        container_id: int,
        user_id: int,
        fields: list[str] | None = None,
    ) -> Self | None:
        """
        Получить активную запись membership для пары (контейнер, пользователь).

        Поиск идёт только по user_id (не по partner_id) — это основной кейс
        для проверки доступа залогиненного юзера. Для поиска по партнёру
        см. get_membership_by_partner().

        fields: по умолчанию — колонки записи без Many2one. Проверкам доступа
        нужны права, is_admin и watermark, а каждая связь в fields — это
        отдельный запрос на догрузку (контейнер, участник, коннектор, аудит).
        Кому нужна связь — передаёт fields явно.

        Returns:
            Экземпляр класса-наследника или None если не найден.
        """
        return await cls.search_one(
            fields=fields or cls.get_store_fields_omit_m2o(),
            filter=[
                (cls._member_res_field, "=", container_id),
                ("user_id", "=", user_id),
                ("is_active", "=", True),
            ],
        )

    @classmethod
    async def check_membership(
        cls,
        container_id: int,
        user_id: int,
    ) -> Self:
        """
        Проверить активное членство и вернуть запись.

        Raises:
            FaraException ACCESS_DENIED (403) если не участник.
        """
        member = await cls.get_membership(container_id, user_id)
        if not member:
            raise FaraException(
                {
                    "content": "ACCESS_DENIED",
                    "status_code": HTTP_403_FORBIDDEN,
                }
            )
        return member

    def has_permissions(self, required: MemberPermissions) -> bool:
        """У участника включено каждое право из набора required."""
        for name, enabled in asdict(required).items():
            if enabled and not getattr(self, name):
                return False
        return True

    @classmethod
    def check_permissions(
        cls,
        member: Self | None,
        required_permission: MemberPermissions | None = None,
    ) -> None:
        """
        Единая точка проверки прав в контейнере: пропускает системного
        админа, админа контейнера и участника, у которого есть права из
        набора required_permission:

            member = await ChatMember.get_membership(chat_id, user_id)
            ChatMember.check_permissions(
                member, ChatPermissions(can_remove=True)
            )

        Без required_permission — только админы.

        Raises:
            FaraException PERMISSION_DENIED (403) если права нет.
        """
        # Системный админ — абсолютный приоритет, членство ему не нужно
        if get_access_session().is_system_admin:
            return

        # Остальным членство обязательно
        if not member:
            cls._raise_forbidden()

        # Админу контейнера можно всё
        if member.is_admin:
            return

        # Обычному участнику — по конкретным правам, если они переданы
        if required_permission and member.has_permissions(required_permission):
            return

        # Ни одно условие не подошло
        cls._raise_forbidden()

    @staticmethod
    def _raise_forbidden() -> NoReturn:
        raise FaraException(
            {
                "content": "PERMISSION_DENIED",
                "status_code": HTTP_403_FORBIDDEN,
            }
        )
