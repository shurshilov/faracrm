import binascii
import hashlib
import re
import secrets
from typing import TYPE_CHECKING, Self

from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.system.dotorm.dotorm.access import (
    get_access_session,
    SUPERUSER,
)
from backend.base.system.dotorm.dotorm.components.filter_parser import (
    FilterExpression,
)
from backend.base.system.dotorm.dotorm.decorators import (
    constrains,
    hybridmethod,
)
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
from backend.base.crm.security.polymorphic_parent import (
    PolymorphicParentMixin,
)
from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.roles import Role
    from backend.base.crm.security.models.workspace import Workspace
    from backend.base.crm.languages.models.language import Language
    from backend.base.crm.leads.models.team_crm import TeamCrm
    from backend.base.crm.partners.models.contact import Contact
    from backend.base.crm.security.routers.sessions import TerminationMode
    from backend.project_setup import ChatConnector
from backend.base.crm.security.models.sessions import Session

# Зарезервированные ID пользователей
ADMIN_USER_ID = 1
SYSTEM_USER_ID = 2
# Шаблон внутреннего пользователя (default_internal)
TEMPLATE_USER_ID = 3
# Anonymous-пользователь для public-эндпоинтов. Не используется для
# реального входа (login невозможен — пустой password_hash). Существует
# в БД чтобы AnonymousSession ссылалась на настоящую запись и можно
# было привязывать к нему ACL/Rules через UI в будущем.
ANONYMOUS_USER_ID = 4


async def _default_roles():
    """Метод для получения ролей по умолчанию"""

    base_user = await env.models.role.search_one(
        filter=[("code", "=", "base_user")],
        fields=["id", "name", "user_ids"],
        fields_nested={"user_ids": {"fields": ["id", "name"]}},
    )
    return [base_user] if base_user else []


# Имя базового «Рабочего места» (сидится в security/app.py вместе с ролью
# base_user). Держим строку синхронной здесь и в сидере.
DEFAULT_WORKSPACE_NAME = "Сотрудник"


async def _default_workspace():
    """Базовое «Рабочее место» — то, что видит Internal User
    (Общение/Партнёры/Активности/Файлы). Проставляется НЕ-админам в
    User._apply_default_workspace (create и create_bulk; админу РМ не нужно —
    он видит всё через байпас); так у обычных юзеров не пустой лаунчер (без
    РМ ничего не видно)."""
    return await env.models.workspace.search_one(
        filter=[("name", "=", DEFAULT_WORKSPACE_NAME)],
        fields=["id", "name"],
    )


async def _default_langs():
    """Метод для получения языков по умолчанию"""

    default_langs = await env.models.language.search(
        filter=[("code", "in", ["en", "ru"]), ("active", "=", True)],
    )
    return default_langs or []


async def _default_lang():
    """Язык по умолчанию для одиночного поля lang_id."""
    return await env.models.language.search_one(
        filter=[("code", "=", "en"), ("active", "=", True)],
    )


class User(PolymorphicParentMixin):
    __table__ = "users"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=256)
    login: str = Char(max_length=50, unique=True)
    password_hash: str = Char(max_length=256, private=True, required=False)
    password_salt: str = Char(max_length=256, private=True, required=False)

    # Администратор (полный доступ ко всему).
    # role_create/role_update=SUPERUSER: ставить/снимать суперпользователя
    # может только суперпользователь — и на создании, и на правке (в т.ч.
    # update_bulk). Value-level правила поверх (нельзя снять флаг с себя и
    # с последнего админа) — @constrains _constrains_admin_demotion.
    is_admin: bool = Boolean(
        default=False, role_create=SUPERUSER, role_update=SUPERUSER
    )

    # Архив вместо удаления (как в Odoo/Django): на users ссылаются 73 FK,
    # физическое удаление — RI-проверки по всем таблицам и RESTRICT у
    # партнёров/проектов/правил маршрутизации. Неактивный не может войти
    # (signin), его сессии закрываются при архивации (update/update_bulk).
    # default_db: на старой базе колонка появляется сразу с true у всех.
    # role_update="system_admin": архивирует администратор настроек.
    active: bool = Boolean(
        default=True,
        default_db=True,
        role_update="system_admin",
        description="Активен (неактивный не может войти)",
    )

    image: Attachment | None = PolymorphicMany2one(relation_table=Attachment)

    # role_update="system_admin": менять роли может только «Администратор
    # настроек» (или суперпользователь — он обходит проверку). Защита от
    # самоповышения привилегий обычным пользователем.
    # default_orm=False: base_user подставляется только в форме
    # (get_default_values); при создании кодом ORM роли не привязывает —
    # Anonymous и портальные пользователи заводятся без base_user, роли им
    # задают явно (сидеры, регистрация).
    role_ids: list["Role"] = Many2many(
        role_update="system_admin",
        default=_default_roles,
        default_orm=False,
        store=False,
        relation_table=lambda: env.models.role,
        many2many_table="user_role_many2many",
        column1="role_id",
        column2="user_id",
        ondelete="cascade",
    )
    # «Рабочее место» (цифровое рабочее место) — курирует, какие приложения
    # пользователь видит в лаунчере. Презентационный слой ПОВЕРХ ролей: не
    # даёт и не отнимает доступ к данным (это ACL/Rules), только видимость
    # меню. NULL → приложений не видно (кроме is_admin — он видит всё через
    # байпас, поэтому РМ ему НЕ назначается). Базовое РМ проставляется
    # не-админам в User.create/create_bulk (не field-default: тот не видит
    # is_admin). Меняется админом (в т.ч. массово через bulk-update списка).
    workspace_id: "Workspace | None" = Many2one(
        relation_table=lambda: env.models.workspace,
        required=False,
        description="Рабочее место (набор видимых приложений)",
    )
    # Каким каналом звонит звонилка в шапке. NULL — внутренний звонок между
    # сотрудниками через WebRTC (он есть всегда и не требует настройки).
    # Заполнен — SIP-коннектор телефонии. Выбор пользователя, не админа.
    call_connector_id: "ChatConnector | None" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        required=False,
        ondelete="set null",
        description="Канал звонков по умолчанию",
    )
    # Команды пользователя (обратная сторона team_crm.user_ids — та же
    # join-таблица). Кладутся в сессию при сборке (как role_ids) для
    # {{team_ids}} — доступ к внешним чатам по командам без запроса на
    # каждую проверку. Инвалидация — publish_roles_changed при смене состава.
    team_ids: list["TeamCrm"] = Many2many(
        store=False,
        relation_table=lambda: env.models.team_crm,
        many2many_table="team_crm_user_many2many",
        column1="team_id",
        column2="user_id",
        ondelete="cascade",
        default=[],
    )
    # Язык интерфейса пользователя (Many2one на Language)
    lang_id: "Language" = Many2one(
        relation_table=lambda: env.models.language,
        required=True,
        description="Язык интерфейса пользователя",
        default=_default_lang,
    )
    # Доступные языки для выбора пользователю. default (en + ru) ORM
    # привязывает после INSERT — и из формы, и при создании кодом
    # (сидеры, регистрация, копирование, импорт), если lang_ids не передан.
    lang_ids: list["Language"] = Many2many(
        store=False,
        relation_table=lambda: env.models.language,
        many2many_table="user_language_many2many",
        column1="language_id",
        column2="user_id",
        ondelete="cascade",
        default=_default_langs,
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

    # @hybridmethod
    # async def create(self, payload: Self) -> int:
    #     """Создание пользователя с автоматическим добавлением языков по умолчанию."""
    #     default_langs = await env.models.language.search(
    #         filter=[("code", "in", ["en", "ru"]), ("active", "=", True)],
    #     )
    #     if default_langs:
    #         payload.lang_id = default_langs[0]
    #         # if not payload.role_ids:
    #         #     # при создании пользователя если не выбрана ни одна роль
    #         #     # то ставим роль внутреннего пользователя по умолчанию
    #         #     base_user = await env.models.role.search(
    #         #         filter=[("code", "=", "base_user")],
    #         #         fields=["id"],
    #         #         limit=1,
    #         #     )

    #         #     if base_user:
    #         #         payload.role_ids = {"selected": base_user}

    #         user_id = await super().create(payload=payload)
    #         # добавить все активные языки как языки к выбору
    #         values = [[user_id, lang.id] for lang in default_langs]
    #         await self.link_many2many(
    #             field=cast(Many2many, User.lang_ids), values=values
    #         )
    #         return user_id
    #     else:
    #         raise ValueError("Language not found for create user")

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
    #         fields_nested={"role_ids": {"fields": ["id"]}},
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

    @constrains("login")
    async def _constrains_login_unique(self, records: list[Self]) -> None:
        """Логин уникален среди всех пользователей — и на create, и на
        update (сменить логин на занятый нельзя), и в bulk-путях: один
        search по всем логинам пачки, дубли внутри пачки ловятся до него.

        Под sudo: пользователь с ограниченной видимостью не должен занять
        логин того, кого не видит. UNIQUE в БД у login нет — проверка здесь.
        """
        taken = FaraException(
            {
                "content": "USER_LOGIN_EXISTS",
                "detail": "User with this login already exists",
                "status_code": 400,
            }
        )
        by_login = {}
        for record in records:
            if not record.login:
                continue
            if record.login in by_login:
                raise taken
            by_login[record.login] = record
        if not by_login:
            return
        existing = await self.sudo().search(
            filter=[("login", "in", list(by_login))], fields=["id", "login"]
        )
        for other in existing:
            if other.id != by_login[other.login].id:
                raise taken

    @staticmethod
    def _only_superuser_changes_admin() -> None:
        """Менять is_admin может только суперпользователь.

        По сути то же, что field-level ACL поля (role_update=SUPERUSER), но
        с кодом для модалки (ONLY_ADMIN_CAN_CHANGE_ADMIN_FIELD) вместо
        общего ACCESS_DENIED. Поэтому зовётся ДО super(): проверка полей
        внутри отдала бы AccessDenied раньше. Системная сессия — без юзера,
        ей можно.
        """
        current = get_access_session().user_id
        if current is not None and not current.is_admin:
            raise FaraException(
                {"content": "ONLY_ADMIN_CAN_CHANGE_ADMIN_FIELD"}
            )

    @constrains("is_admin")
    async def _constrains_admin_demotion(self, records: list[Self]) -> None:
        """Снять флаг суперпользователя нельзя с себя и с последнего админа.

        Кто вообще вправе трогать is_admin, решают раньше field-level ACL
        поля и _only_superuser_changes_admin. Одна функция на update и
        update_bulk: снимаемые считаются пачкой, и последний админ — с
        учётом всей пачки. На create снятия нет.
        """
        ids = [r.id for r in records if r.id and r.is_admin is False]
        if not ids:
            return
        demoted = [
            user.id
            for user in await self.sudo().search(
                filter=[("id", "in", ids), ("is_admin", "=", True)],
                fields=["id"],
            )
        ]
        if not demoted:
            return
        current = get_access_session().user_id
        if current is not None and current.id in demoted:
            raise FaraException(
                {"content": "YOU_CANNOT_REVOKE_YOUR_OWN_ADMIN_STATUS"}
            )
        admins = await self.sudo().search_count(
            filter=[("is_admin", "=", True)]
        )
        if admins - len(demoted) < 1:
            raise FaraException(
                {"content": "CANNOT_REMOVE_THE_LAST_ADMINISTRATOR"}
            )

    @constrains("active")
    async def _constrains_archive_self(self, records: list[Self]) -> None:
        """Архивировать себя нельзя: сессии закрылись бы этим же запросом.
        Одна функция на update и update_bulk."""
        current = get_access_session().user_id
        if current is None:
            return
        for record in records:
            if record.id == current.id and record.active is False:
                raise FaraException({"content": "YOU_CANNOT_ARCHIVE_YOURSELF"})

    @classmethod
    async def _apply_default_workspace(cls, payloads: list["User"]) -> None:
        """Базовое «Рабочее место» НЕ-админам без явного workspace_id — один
        поиск РМ на всю пачку. Одна реализация для create и create_bulk
        (админ видит всё через байпас, РМ ему не нужно; field-default так не
        сделать — он не видит is_admin). Явно заданное РМ не трогаем."""
        todo = [
            p
            for p in payloads
            if not p.is_admin and "workspace_id" not in p.assigned_fields()
        ]
        if not todo:
            return
        default_ws = await _default_workspace()
        if default_ws:
            for p in todo:
                p.workspace_id = default_ws

    @hybridmethod
    async def create(
        self, payload: Self, session=None, depends_jobs=None
    ) -> int:
        """Создание пользователя (уникальность login — @constrains выше)."""
        await self._apply_default_workspace([payload])
        return await super().create(payload, session, depends_jobs)

    @hybridmethod
    async def create_bulk(
        self, payload: list[Self], session=None, depends_jobs=None
    ):
        await self._apply_default_workspace(payload)
        return await super().create_bulk(payload, session, depends_jobs)

    async def update(
        self,
        payload: "User",
        fields: list[str] | None = None,
        session=None,
        depends_jobs=None,
    ):
        # Берем переданные поля или автоматически вычисляем заполненные.
        fields = fields or payload.assigned_fields()

        # Смена флага не-суперпользователем — с понятным кодом, до ACL.
        # Остальное про is_admin (снятие с себя / с последнего) — в
        # @constrains _constrains_admin_demotion внутри super().update.
        if "is_admin" in fields and payload.is_admin != self.is_admin:
            self._only_superuser_changes_admin()

        await super().update(payload, fields, session, depends_jobs)

        # Изменились authz-атрибуты (роли/суперюзер) → инвалидируем
        # кэш сессий этого юзера через шину, чтобы воркеры пересобрали
        # сессию со свежими ролями (а не держали устаревшие до TTL).
        if "role_ids" in fields or "is_admin" in fields:
            await Session.publish_roles_changed([self.id])
        # Архивация → закрыть все сессии (войти заново он не сможет).
        if "active" in fields and payload.active is False:
            await Session.terminate_for_users([self.id])

    @hybridmethod
    async def update_bulk(
        self, ids: list[int], payload: "User", session=None, depends_jobs=None
    ):
        # Записей на руках нет — по присутствию поля, как field-level ACL.
        if "is_admin" in payload.assigned_fields():
            self._only_superuser_changes_admin()
        result = await super().update_bulk(ids, payload, session, depends_jobs)
        # role_ids через bulk не идёт (store=False); is_admin — идёт.
        if "is_admin" in payload.assigned_fields():
            await Session.publish_roles_changed(list(ids))
        if payload.active is False:
            await Session.terminate_for_users(list(ids))
        return result

    @classmethod
    async def get_all_role_codes(cls, user_id: int) -> list[tuple[int, str]]:
        """Роли пользователя (id + code), развёрнутые по based_role_ids.

        Возвращает пары (id, code): id нужен чтобы роли в сессии
        (session.user_id.role_ids) были ПОЛНОЦЕННЫМИ объектами Role, а не
        стабами {code} — иначе сериализация ответа (напр. default_values,
        где user_id = текущий юзер из сессии) падает на required-поле
        role_ids[].id. code используется field-level проверкой доступа.
        Один рекурсивный CTE — тот же, что в SecurityAccessChecker
        ._get_user_roles, который читает роли из сессии вместо запроса:
        поэтому здесь отдаются ВСЕ роли, и без code тоже (потребители
        кода фильтруют `if r.code` сами).
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
            SELECT DISTINCT r.id, r.code
            FROM roles r
            JOIN role_tree t ON r.id = t.role_id
        """
        session = cls._get_db_session()
        result = await session.execute(query, [user_id], cursor="fetch")
        return [
            (row["id"], row["code"])
            for row in result
            if row.get("id") is not None
        ]

    @classmethod
    async def get_all_team_ids(cls, user_id: int) -> list[int]:
        """ID команд пользователя (team_crm.user_ids). Кладутся в сессию при
        сборке для {{team_ids}} — без запроса на каждую проверку доступа.
        Прямой запрос по join-таблице (не рекурсивный)."""
        query = (
            "SELECT team_id FROM team_crm_user_many2many WHERE user_id = $1"
        )
        session = cls._get_db_session()
        result = await session.execute(query, [user_id], cursor="fetch")
        return [row["team_id"] for row in result if row.get("team_id")]

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

            # закрыть старые сессии — под sudo: это побочный эффект смены
            # пароля над СВОИМИ сессиями (terminate_sessions фильтрует по
            # user_id = self.id), а ACL на sessions есть не у всех: у
            # портальной роли его нет, и смена пароля падала с отказом.
            if auth_session is None:
                await self.sudo().terminate_sessions()
            else:
                await self.sudo().terminate_sessions(auth_session.id)

    async def terminate_sessions(
        self,
        exclude_session_id: int | None = None,
        mode: "TerminationMode | str" = "MY",
    ) -> int:
        """
        Завершить все активные сессии пользователя.

        Args:
            session: DB session
            exclude_token: Токен сессии, которую не нужно завершать

        Returns:
            Количество завершённых сессий
        """
        # Lazy импорт чтобы избежать цикла на верхнем уровне:
        # users.py ↔ security.routers.sessions
        from backend.base.crm.security.routers.sessions import TerminationMode

        # Принимаем как Enum, так и строку (default = "MY" чтобы не
        # тянуть Enum в default-значение сигнатуры)
        if isinstance(mode, str):
            mode = TerminationMode(mode)

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

        # Инвалидируем кэш на всех воркерах через pg_notify
        if env.apps.auth.session_cache_enabled:
            await Session.publish_revoked(ids_to_terminate)

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
