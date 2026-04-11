import binascii
import hashlib
import re
import secrets
from typing import TYPE_CHECKING, Self, cast

from backend.base.crm.attachments.models.attachments import Attachment
from ....system.dotorm.dotorm.components.filter_parser import FilterExpression
from ...security.routers.sessions import TerminationMode
from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
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
    from backend.base.crm.partners.models.contact import Contact
from backend.base.crm.security.models.sessions import Session

# Зарезервированные ID пользователей
ADMIN_USER_ID = 1
SYSTEM_USER_ID = 2
TEMPLATE_USER_ID = 3  # Шаблон внутреннего пользователя (default_internal)


async def default_roles():
    """Метод для получения ролей по умолчанию"""
    base_user = await env.models.role.search(
        filter=[("code", "=", "base_user")],
        fields=["id", "name", "user_ids"],
        fields_nested={"user_ids": ["id", "name"]},
        limit=1,
    )
    return base_user or []


class User(DotModel):
    __table__ = "users"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=256)
    login: str = Char(max_length=50)
    password_hash: str = Char(max_length=256, schema_required=False)
    password_salt: str = Char(max_length=256, schema_required=False)

    # Администратор (полный доступ ко всему)
    is_admin: bool = Boolean(default=False)

    image: Attachment | None = PolymorphicMany2one(relation_table=Attachment)

    role_ids: list["Role"] = Many2many(
        default=default_roles,
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

    # Настройки уведомлений
    notification_popup: bool = Boolean(
        default=True,
        description="Показывать всплывающие уведомления",
    )
    notification_sound: bool = Boolean(
        default=True,
        description="Воспроизводить звук уведомлений",
    )

    @hybridmethod
    async def create(self, payload: Self) -> int:
        """Создание пользователя с автоматическим добавлением языков по умолчанию."""
        default_langs = await env.models.language.search(
            filter=[("code", "in", ["en", "ru"]), ("active", "=", True)],
        )
        if default_langs:
            payload.lang_id = default_langs[0]
            # if not payload.role_ids:
            #     # при создании пользователя если не выбрана ни одна роль
            #     # то ставим роль внутреннего пользователя по умолчанию
            #     base_user = await env.models.role.search(
            #         filter=[("code", "=", "base_user")],
            #         fields=["id"],
            #         limit=1,
            #     )

            #     if base_user:
            #         payload.role_ids = {"selected": base_user}

            user_id = await super().create(payload=payload)
            # добавить все активные языки как языки к выбору
            values = [[user_id, lang.id] for lang in default_langs]
            await self.link_many2many(
                field=cast(Many2many, User.lang_ids), values=values
            )
            return user_id
        else:
            raise ValueError("Language not found for create user")

    # @hybridmethod
    # async def create_from_template(
    #     self,
    #     name: str,
    #     login: str,
    #     password: str,
    #     template_id: int = TEMPLATE_USER_ID,
    # ) -> int:
    #     """
    #     Создаёт нового внутреннего пользователя на основе шаблона.

    #     копирует настройки (home_page, layout_theme, уведомления)
    #     и роли из шаблона, затем создаёт нового пользователя.

    #     Args:
    #         name:        Отображаемое имя пользователя
    #         login:       Логин (уникальный)
    #         password:    Пароль в открытом виде (будет захэширован)
    #         template_id: ID шаблона (по умолчанию TEMPLATE_USER_ID=3)

    #     Returns:
    #         ID созданного пользователя

    #     Пример использования:
    #         user_id = await User.create_from_template(
    #             name="Иван Иванов",
    #             login="ivan.ivanov",
    #             password="secret123",
    #         )
    #     """
    #     # 1. Загружаем шаблон
    #     template = await env.models.user.get(
    #         template_id,
    #         fields=[
    #             "id",
    #             "role_ids",
    #             "home_page",
    #             "layout_theme",
    #             "notification_popup",
    #             "notification_sound",
    #         ],
    #         fields_nested={"role_ids": ["id"]},
    #     )

    #     # 2. Генерируем хэш пароля
    #     salt = secrets.token_hex(64)
    #     password_hash = self.generate_password_hash(password, salt)

    #     # 3. Берём настройки из шаблона (или дефолтные если шаблон не найден)
    #     home_page = template.home_page
    #     layout_theme = template.layout_theme
    #     notification_popup = template.notification_popup
    #     notification_sound = template.notification_sound
    #     role_ids = [r.id for r in template.role_ids]
    #     # 4. Создаём пользователя
    #     user_id = await env.models.user.create(
    #         payload=User(
    #             name=name,
    #             login=login,
    #             is_admin=False,
    #             password_hash=password_hash,
    #             password_salt=salt,
    #             home_page=home_page,
    #             layout_theme=layout_theme,
    #             notification_popup=notification_popup,
    #             notification_sound=notification_sound,
    #             role_ids={"selected": role_ids},
    #         )
    #     )
    #     return user_id

    def generate_password_hash_salt_old(self, password: str):
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

    _DEFAULT_PASSWORD_POLICY = {
        "min_length": 5,
        "require_uppercase": False,
        "require_lowercase": False,
        "require_digits": False,
        "require_special": False,
    }

    @staticmethod
    async def get_password_policy(env: "Environment") -> dict:
        """Получить текущую парольную политику из SystemSettings."""
        raw = await env.models.system_settings.get_value(
            "auth.password_policy"
        )
        default = User._DEFAULT_PASSWORD_POLICY
        if not raw or not isinstance(raw, dict):
            return default.copy()
        return {
            "min_length": raw.get("min_length", default["min_length"]),
            "require_uppercase": raw.get(
                "require_uppercase", default["require_uppercase"]
            ),
            "require_lowercase": raw.get(
                "require_lowercase", default["require_lowercase"]
            ),
            "require_digits": raw.get(
                "require_digits", default["require_digits"]
            ),
            "require_special": raw.get(
                "require_special", default["require_special"]
            ),
        }

    @staticmethod
    def validate_password(password: str, policy: dict) -> list[str]:
        """
        Проверить пароль по политике.
        Возвращает список кодов ошибок (пустой = валидный).
        """
        errors: list[str] = []
        min_len = policy.get("min_length", 5)
        if len(password) < min_len:
            errors.append(f"too_short:{min_len}")
        if policy.get("require_uppercase"):
            if not re.search(r"[A-ZА-ЯЁ]", password):
                errors.append("no_uppercase")
        if policy.get("require_lowercase"):
            if not re.search(r"[a-zа-яё]", password):
                errors.append("no_lowercase")
        if policy.get("require_digits"):
            if not re.search(r"[0-9]", password):
                errors.append("no_digit")
        if policy.get("require_special"):
            if not re.search(
                r"""[!@#$%^&*()_+\-=\[\]{}|;:'",.<>?/\\`~]""", password
            ):
                errors.append("no_special")
        return errors

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

        async with env.apps.db.get_transaction():
            # сохранить хеш-пароль, соль
            await self.update(
                payload=User(
                    password_hash=hash,
                    password_salt=salt,
                )
            )

            # закрыть старые сессии
            if auth_session is None:
                await self.terminate_sessions()
            else:
                await self.terminate_sessions(auth_session.id)

    async def terminate_sessions(
        self,
        exclude_session_id: int | None = None,
        mode: TerminationMode = TerminationMode.MY,
    ) -> int:
        """
        Завершить все активные сессии пользователя.

        Args:
            session: DB session
            exclude_token: Токен сессии, которую не нужно завершать

        Returns:
            Количество завершённых сессий
        """
        filter: FilterExpression = [("active", "=", True)]
        if mode == TerminationMode.MY:
            filter.append(("user_id", "=", self.id))

        # Найти все активные сессии пользователя
        active_sessions = await Session.search(
            filter=filter,
            fields=["id", "token"],
        )

        # Отфильтровать текущую сессию если нужно
        ids_to_terminate = [
            s.id
            for s in active_sessions
            if exclude_session_id is None or s.id != exclude_session_id
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

        session = self._get_db_session()
        result = await session.execute(query, [self.id], cursor="fetch")
        return [row["role_id"] for row in result]
