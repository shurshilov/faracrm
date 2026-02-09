from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Datetime,
    Integer,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.crm.security.exceptions import AuthException

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
from backend.base.system.core.enviroment import env


class _SystemUser:
    """Системный пользователь для post_init операций."""

    def __init__(self, user_id: int):
        self.id = user_id
        self.is_admin = True


class SystemSession:
    """
    Системная сессия для инициализации.

    Используется в post_init для выполнения операций
    от имени системного пользователя.

    Args:
        user_id: ID системного пользователя
    """

    def __init__(self, user_id: int):
        self.user_id = _SystemUser(user_id)


class Session(DotModel):
    __table__ = "sessions"

    # Значение по умолчанию — 1 день (используется если system_settings недоступен)
    DEFAULT_TTL = 60 * 60 * 24 * 1

    id: int = Integer(primary_key=True)
    active: bool = Boolean(default=True)
    user_id: "User" = Many2one(relation_table=lambda: env.models.user)
    token: str = Char(max_length=256, index=True)
    ttl: int = Integer()
    expired_datetime: datetime | None = Datetime()

    create_datetime: datetime = Datetime(default=datetime.now(timezone.utc))
    create_user_id: "User" = Many2one(relation_table=lambda: env.models.user)
    update_datetime: datetime = Datetime(default=datetime.now(timezone.utc))
    update_user_id: "User" = Many2one(relation_table=lambda: env.models.user)

    @classmethod
    async def get_ttl(cls) -> int:
        """Получить TTL сессии из системных настроек."""
        try:
            value = await env.models.system_settings.get_value(
                "auth.session_ttl", cls.DEFAULT_TTL
            )
            return int(value)
        except Exception:
            return cls.DEFAULT_TTL

    @hybridmethod
    async def session_check(self, token: str):
        """Метод проверяет валидность сессии.
        1. Проверить существование активной сессии по токену
        2. Проверить истекла сессии или нет
        """
        session = self._get_db_session()

        # Прямой SQL для получения сессии с данными пользователя
        stmt = """
            SELECT
                s.id,
                s.ttl,
                s.create_datetime,
                s.expired_datetime,
                s.active,
                u.id as user_id,
                u.is_admin,
                u.name
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = %s AND s.active = true
            LIMIT 1
        """

        result = await session.execute(stmt, [token])

        if not result:
            raise AuthException.SessionNotExist()

        session_id = result[0]
        now = datetime.now(timezone.utc)
        # expired = session_id["create_datetime"] + timedelta(
        #     seconds=session_id["ttl"]
        # )
        expired = session_id["expired_datetime"]

        if expired < now:
            # Деактивируем сессию
            await session.execute(
                "UPDATE sessions SET active = false WHERE id = %s",
                [session_id["id"]],
            )
            raise AuthException.SessionExpired()

        # Создаём объект сессии с user_id содержащим is_admin
        session_obj = Session(
            id=session_id["id"],
            ttl=session_id["ttl"],
            create_datetime=session_id["create_datetime"],
            active=session_id["active"],
            user_id=env.models.user(
                id=session_id["user_id"],
                is_admin=session_id["is_admin"],
                name=session_id["name"],
            ),
        )

        return session_obj
