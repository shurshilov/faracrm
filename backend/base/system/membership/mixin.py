# Copyright 2025 FARA CRM
# Generic polymorphic membership mixin.

from datetime import datetime, timezone
from typing import TYPE_CHECKING, ClassVar, Self

from starlette.status import HTTP_403_FORBIDDEN

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Datetime,
    Many2one,
)
from ..dotorm.dotorm.model import DotModel

if TYPE_CHECKING:
    from backend.base.crm.partners.models.partners import Partner
    from backend.base.crm.users.models.users import User


class MemberMixin(DotModel):
    """
    Миксин для моделей-мемберов полиморфного membership.

    Предоставляет:
      • общие поля: user_id, partner_id, is_active, is_admin, joined_at, left_at
      • методы членства: get_membership / check_membership
      • методы прав: has_permission / check_permission
      • шорткаты: check_admin

    Модель-наследник ДОЛЖЕН объявить:
      __table__ — имя таблицы (например "chat_member")
      _member_res_field — имя FK колонки на контейнер (например "chat_id")
      _member_res_model — lazy-геттер модели-контейнера
                         (обычно: `lambda: env.models.chat`)

    Модель-наследник МОЖЕТ объявить:
      id — если нужен кастомный primary key (иначе возьми Integer(primary_key=True))
      FK на контейнер — отдельным Many2one (миксин НЕ создаёт его сам,
                        потому что у каждой модели своё имя колонки)
      can_* поля — обычные Boolean-колонки, которые будут автоматически
                   распознаны методом has_permission()
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

    def has_permission(self, permission: str) -> bool:
        """
        Проверить есть ли у участника конкретное право.
        Админ (is_admin=True) имеет все права.

        Args:
            permission: имя булева поля — обычно с префиксом "can_"
                        (can_read, can_write, can_pin, ...) или "is_admin"

        Returns:
            True если право есть, False если нет или поля не существует.
        """
        if self.is_admin:
            return True
        return bool(getattr(self, permission, False))

    def get_permissions(self) -> dict[str, bool]:
        """
        Собрать словарь всех can_* прав + is_admin.
        Админ перекрывает все can_* в True.

        Автоматически находит все атрибуты, начинающиеся на 'can_',
        так что при добавлении нового can_-поля метод НЕ надо править.
        """
        result: dict[str, bool] = {"is_admin": self.is_admin}
        for attr in dir(self):
            if attr.startswith("can_"):
                value = getattr(self, attr, False)
                if isinstance(value, bool):
                    result[attr] = value or self.is_admin
        return result

    @classmethod
    async def get_membership(
        cls,
        container_id: int,
        user_id: int,
    ) -> Self | None:
        """
        Получить активную запись membership для пары (контейнер, пользователь).

        Поиск идёт только по user_id (не по partner_id) — это основной кейс
        для проверки доступа залогиненного юзера. Для поиска по партнёру
        см. get_membership_by_partner().

        Returns:
            Экземпляр класса-наследника или None если не найден.
        """
        result = await cls.search(
            filter=[
                (cls._member_res_field, "=", container_id),
                ("user_id", "=", user_id),
                ("is_active", "=", True),
            ],
            limit=1,
        )
        return result[0] if result else None

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

    @classmethod
    async def check_permission(
        cls,
        container_id: int,
        user_id: int,
        permission: str,
    ):
        """
        Проверить членство + конкретное право.

        Args:
            permission: имя boolean-поля (can_read / can_write / is_admin / ...).

        Raises:
            FaraException ACCESS_DENIED если не член.
            FaraException PERMISSION_DENIED если нет права.
        """
        member = await cls.check_membership(container_id, user_id)
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
        container_id: int,
        user_id: int,
    ):
        """
        Шорткат: проверить, что пользователь — админ контейнера.

        Raises:
            FaraException ACCESS_DENIED если не член.
            FaraException ADMIN_REQUIRED если не админ.
        """
        member = await cls.check_membership(container_id, user_id)
        if not member.is_admin:
            raise FaraException(
                {
                    "content": "ADMIN_REQUIRED",
                    "status_code": HTTP_403_FORBIDDEN,
                }
            )
        return member
