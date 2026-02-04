import binascii
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import TYPE_CHECKING, Self, cast

from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    PolymorphicOne2many,
    Boolean,
    Char,
    PolymorphicMany2one,
    Integer,
    Many2many,
    Many2one,
    One2many,
    Selection,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.roles import Role
    from backend.base.crm.languages.models.language import Language
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.partners.models.contact import Contact
from backend.base.crm.security.models.sessions import Session


# Зарезервированные ID пользователей
ADMIN_USER_ID = 1
SYSTEM_USER_ID = 2


class User(DotModel):
    __table__ = "users"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=256)
    login: str = Char(max_length=50)
    # email: str = Char(max_length=100)
    password_hash: str = Char(max_length=256, schema_required=False)
    password_salt: str = Char(max_length=256, schema_required=False)

    # Администратор (полный доступ ко всему)
    is_admin: bool = Boolean(default=False)

    image: Attachment | None = PolymorphicMany2one(relation_table=Attachment)
    image_ids: list[Attachment] = PolymorphicOne2many(
        store=False,
        relation_table=Attachment,
        relation_table_field="res_id",
        default=None,
    )
    role_ids: list["Role"] = Many2many(
        store=False,
        relation_table=lambda: env.models.role,
        many2many_table="user_role_many2many",
        column1="role_id",
        column2="user_id",
        ondelete="cascade",
    )
    # Язык интерфейса пользователя (Many2one на Language)
    lang_id: "Language" = Many2one(
        relation_table=lambda: env.models.language,
        required=True,
        description="Язык интерфейса пользователя",
    )
    # Доступные языки для выбора пользователю
    lang_ids: list["Language"] = Many2many(
        store=False,
        relation_table=lambda: env.models.language,
        many2many_table="user_language_many2many",
        column1="language_id",
        column2="user_id",
        ondelete="cascade",
    )

    # Коннекторы, с которыми работает оператор
    # DEPRECATED: Управление операторами только через ChatConnector.operator_ids
    # connector_ids: list["ChatConnector"] = Many2many(
    #     store=False,
    #     relation_table=lambda: env.models.chat_connector,
    #     many2many_table="chat_connector_operator_many2many",
    #     column1="connector_id",
    #     column2="user_id",
    #     ondelete="cascade",
    #     description="Коннекторы, с которыми работает оператор",
    # )

    # Контакты (телефоны, email, telegram и т.д.)
    contact_ids: list["Contact"] = One2many(
        store=False,
        relation_table=lambda: env.models.contact,
        relation_table_field="user_id",
        description="Контакты",
    )

    # Страница по умолчанию после входа (относительный маршрут, например /sale или /chat)
    home_page: str = Char(
        max_length=256,
        required=False,
        default="/users",
        description="Страница по умолчанию",
    )

    # Тема интерфейса (classic — боковое меню, modern — app launcher)
    layout_theme: str = Selection(
        options=[
            ("classic", "Классическая"),
            ("modern", "Современная"),
        ],
        default="modern",
        description="Тема интерфейса",
    )

    @hybridmethod
    async def create(self, payload: Self) -> int:
        """Создание пользователя с автоматическим добавлением языков по умолчанию."""
        default_langs = await env.models.language.search(
            filter=[("code", "in", ["en", "ru"]), ("active", "=", True)],
        )
        if default_langs:
            payload.lang_id = default_langs[0]
            user_id = await super().create(payload=payload)
            # добавить все активные языки как языки к выбору
            values = [[user_id, lang.id] for lang in default_langs]
            await self.link_many2many(
                field=cast(Many2many, User.lang_ids), values=values
            )
            return user_id
        else:
            raise ValueError("Language not found for create user")

    def generate_password_hash_salt_old(self, password: str):
        """
        Используется для сравнения введенного пароля пользователя
        в процессе аутентификации. Для успешного сравнения соль
        необходимо использовать такую же что и при создании хеша пароля
        """
        return self.generate_password_hash(password, self.password_salt)

    def generate_password_hash(self, password: str, salt: str):
        """Генерирует хеш, для безопасного хранения пароля"""
        return binascii.hexlify(
            hashlib.pbkdf2_hmac(
                "sha512",
                password.encode(),
                salt.encode(),
                10000,
            )
        ).decode()

    async def password_change(
        self,
        env: "Environment",
        password: str,
        auth_session: Session | None = None,
    ):
        """
        Метод смены пароля.
        Генерация соли с использованием
        Cryptographically Secure Pseudo-Random Number Generator (CSPRNG)

        Возвращает новый токен сессии
        """

        salt = secrets.token_hex(64)
        hash = self.generate_password_hash(password, salt)
        # token = secrets.token_urlsafe(nbytes=64)

        async with env.apps.db.get_transaction():
            # сохранить хеш-пароль, соль
            self.password_hash = hash
            self.password_salt = salt
            await self.update()

            # закрыть старые сессии
            if auth_session is None:
                await self.terminate_sessions()
            else:
                await self.terminate_sessions(auth_session.token)

            # now = datetime.now(timezone.utc)
            # создать сессию
            # new_session = Session(
            #     user_id=self,
            #     token=token,
            #     ttl=Session._ttl,
            #     expired_datetime=now + timedelta(seconds=Session._ttl),
            #     create_user_id=auth_user_id,
            #     update_user_id=auth_user_id,
            # )
            # await env.models.session.create(payload=new_session)
            # return token

    async def terminate_sessions(
        self,
        exclude_token: str | None = None,
    ) -> int:
        """
        Завершить все активные сессии пользователя.

        Args:
            session: DB session
            exclude_token: Токен сессии, которую не нужно завершать

        Returns:
            Количество завершённых сессий
        """
        # Найти все активные сессии пользователя
        active_sessions = await Session.search(
            filter=[("user_id", "=", self.id), ("active", "=", True)],
            fields=["id", "token"],
        )

        # Отфильтровать текущую сессию если нужно
        ids_to_terminate = [
            s.id
            for s in active_sessions
            if exclude_token is None or s.token != exclude_token
        ]

        if not ids_to_terminate:
            return 0

        # Bulk update - деактивируем все сессии
        await Session.update_bulk(
            ids=ids_to_terminate,
            payload=Session(active=False),
        )

        return len(ids_to_terminate)

    async def get_all_roles(self) -> list[int]:
        """
        Собирает все роли пользователя включая based_role_ids рекурсивно.

        Использует рекурсивный CTE — один запрос.

        Returns:
            Список ID всех ролей (прямые + все based)
        """
        query = """
            WITH RECURSIVE role_tree AS (
                SELECT role_id
                FROM user_role_many2many
                WHERE user_id = $1
                
                UNION
                
                SELECT rb.based_role_id
                FROM role_tree rt
                JOIN role_based_many2many rb ON rb.role_id = rt.role_id
            )
            SELECT DISTINCT role_id FROM role_tree
        """

        session = env.apps.db.get_session()
        result = await session.execute(query, [self.id], cursor="fetch")
        return [row["role_id"] for row in result]
