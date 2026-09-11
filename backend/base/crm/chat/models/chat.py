# Copyright 2025 FARA CRM
# Chat module - main chat/channel model

from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Text,
    Boolean,
    Datetime,
    Selection,
    Many2one,
    One2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.users.audit_mixin import AuditMixin

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_message import ChatMessage
    from backend.base.crm.chat.models.chat_member import ChatMember
    from backend.base.crm.chat.models.chat_external_chat import (
        ChatExternalChat,
    )
    from backend.base.crm.leads.models.team_crm import TeamCrm


# Права по умолчанию для разных типов чатов
DEFAULT_PERMISSIONS = {
    "direct": {
        # В личном чате оба могут всё кроме приглашения и удаления чужих
        "can_read": True,
        "can_write": True,
        "can_invite": False,
        "can_pin": True,
        "can_delete_others": False,
        "is_admin": False,
    },
    "group": {
        # В группе обычный участник
        "can_read": True,
        "can_write": True,
        "can_invite": False,
        "can_pin": False,
        "can_delete_others": False,
        "is_admin": False,
    },
    "channel": {
        # В канале по умолчанию только чтение
        "can_read": True,
        "can_write": False,
        "can_invite": False,
        "can_pin": False,
        "can_delete_others": False,
        "is_admin": False,
    },
    "record": {
        # Чат привязанный к записи - обычные права
        "can_read": True,
        "can_write": True,
        "can_invite": False,
        "can_pin": False,
        "can_delete_others": False,
        "is_admin": False,
    },
}

# Права создателя/админа
CREATOR_PERMISSIONS = {
    "can_read": True,
    "can_write": True,
    "can_invite": True,
    "can_pin": True,
    "can_delete_others": True,
    "is_admin": True,
}


class Chat(AuditMixin, DotModel):
    """
    Chat model

    Типы чатов:
    - direct: прямой чат между двумя пользователями
    - group: групповой чат с несколькими участниками
    - channel: публичный или приватный канал
    - record: чат привязанный к сущности
    """

    __table__ = "chat"
    # Отключаем публичные /auto/chat/... эндпоинты.
    __auto_crud__ = False

    # Составной индекс для поиска record-чата записи:
    # вызывается при каждом открытии формы любой записи
    # через /records/{res_model}/{res_id}/chat/exists.
    __indexes__ = [("res_model", "res_id", "chat_type")]

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=255, description="Название чата/канала")
    description: str | None = Text(description="Описание канала")

    # Тип чата
    chat_type: str = Selection(
        options=[
            ("direct", "direct"),
            ("group", "group"),
            ("channel", "channel"),
            ("record", "record"),
        ],
        default="direct",
        description="""Тип чата: direct - личный, group - группа,
        channel - канал, record - привязан к записе в базе""",
    )

    # Статус и настройки
    active: bool = Boolean(default=True)
    is_public: bool = Boolean(
        default=False, description="Публичный канал доступен всем"
    )

    # Классификация: внутренний/внешний (пересчитывается триггером)
    is_internal: bool = Boolean(
        default=True,
        description="True = только Users, False = есть Partners",
    )

    # === Права по умолчанию для новых участников ===
    default_can_read: bool = Boolean(
        default=True, description="Право чтения по умолчанию"
    )
    default_can_write: bool = Boolean(
        default=True, description="Право записи по умолчанию"
    )
    default_can_invite: bool = Boolean(
        default=False, description="Право приглашения по умолчанию"
    )
    default_can_pin: bool = Boolean(
        default=False, description="Право закрепления по умолчанию"
    )
    default_can_delete_others: bool = Boolean(
        default=False,
        description="Право удаления чужих сообщений по умолчанию",
    )

    last_message_date: datetime | None = Datetime(
        description="Дата последнего сообщения"
    )

    # Участники чата (one2many к ChatMember)
    member_ids: list["ChatMember"] = One2many(
        store=False,
        relation_table=lambda: env.models.chat_member,
        relation_table_field="chat_id",
        description="Участники чата",
    )

    # Сообщения чата (one2many)
    message_ids: list["ChatMessage"] = One2many(
        store=False,
        relation_table=lambda: env.models.chat_message,
        relation_table_field="chat_id",
        description="Сообщения чата",
    )

    # Внешние чаты (связь с внешними системами)
    external_chat_ids: list["ChatExternalChat"] = One2many(
        store=False,
        relation_table=lambda: env.models.chat_external_chat,
        relation_table_field="chat_id",
        description="Связанные внешние чаты",
    )

    # Привязка к записи (для chat_type='record')
    res_model: str | None = Char(
        description="Модель записи (lead, task, partner...) — для record-чатов",
    )
    res_id: int | None = Integer(
        description="ID записи — для record-чатов",
    )

    # Команда-владелец чата — ось team-scoped доступа. Штампуется из
    # connector.team_id при создании клиентского чата. NULL у внутренних чатов
    # (is_internal=true) → в team-гейт не попадают, видны только по членству.
    # index=True: get_chats фильтрует c.team_id = ANY(...) на каждый рендер.
    team_id: "TeamCrm | None" = Many2one(
        relation_table=lambda: env.models.team_crm,
        ondelete="set null",
        index=True,
        description="Команда-владелец чата (team-scoped доступ)",
    )

    def get_default_permissions(self) -> dict:
        """Получить права по умолчанию для данного чата."""
        return {
            "can_read": self.default_can_read,
            "can_write": self.default_can_write,
            "can_invite": self.default_can_invite,
            "can_pin": self.default_can_pin,
            "can_delete_others": self.default_can_delete_others,
            "is_admin": False,
        }

    @classmethod
    def get_type_default_permissions(cls, chat_type: str) -> dict:
        """Получить права по умолчанию для типа чата."""
        return DEFAULT_PERMISSIONS.get(chat_type, DEFAULT_PERMISSIONS["group"])

    @hybridmethod
    async def create_direct_chat(self, user1_id: int, user2_id: int):
        """
        Создать или найти существующий прямой чат между двумя пользователями.
        """
        # Ищем существующий прямой чат между этими пользователями
        existing = await self._find_direct_chat(user1_id, user2_id)
        if existing:
            return existing

        # Создаём новый чат с правами по умолчанию для direct
        # TODO: gather
        user1 = await env.models.user.get(user1_id)
        user2 = await env.models.user.get(user2_id)

        default_perms = DEFAULT_PERMISSIONS["direct"]

        now = datetime.now(timezone.utc)
        chat = Chat(
            # name=f"{user1.name} - {user2.name}",
            name=f"{user2.name}",
            chat_type="direct",
            create_user_id=user1,
            create_datetime=now,
            update_datetime=now,
            # Права по умолчанию
            default_can_read=default_perms["can_read"],
            default_can_write=default_perms["can_write"],
            default_can_invite=default_perms["can_invite"],
            default_can_pin=default_perms["can_pin"],
            default_can_delete_others=default_perms["can_delete_others"],
        )
        chat.id = await self.create(payload=chat)

        # В direct чате оба пользователя имеют одинаковые права
        await self._add_user_member(chat.id, user1_id, default_perms)
        await self._add_user_member(chat.id, user2_id, default_perms)

        return chat

    async def _find_direct_chat(
        self, user1_id: int, user2_id: int
    ) -> "Chat | None":
        """Найти существующий прямой чат между двумя пользователями."""
        session = self._get_db_session()
        query = """
            SELECT c.id, c.name, c.chat_type,
                c.create_user_id, c.create_datetime, c.update_datetime,
                c.default_can_read, c.default_can_write, c.default_can_invite,
                c.default_can_pin, c.default_can_delete_others
            FROM chat c
            JOIN chat_member cm1 ON c.id = cm1.chat_id
                AND cm1.user_id = %s AND cm1.is_active = true
            JOIN chat_member cm2 ON c.id = cm2.chat_id
                AND cm2.user_id = %s AND cm2.is_active = true
            WHERE c.chat_type = 'direct' AND c.active = true
            LIMIT 1
        """
        result = await session.execute(query, (user1_id, user2_id))
        if result:
            return Chat(**result[0])
        else:
            return None

    @hybridmethod
    async def create_group_chat(
        self, name: str, creator_id: int, member_ids: list[int]
    ):
        """Создать групповой чат."""
        creator = env.models.user(id=creator_id)

        default_perms = DEFAULT_PERMISSIONS["group"]

        now = datetime.now(timezone.utc)
        chat = Chat(
            name=name,
            chat_type="group",
            create_user_id=creator,
            create_datetime=now,
            update_datetime=now,
            # Права по умолчанию
            default_can_read=default_perms["can_read"],
            default_can_write=default_perms["can_write"],
            default_can_invite=default_perms["can_invite"],
            default_can_pin=default_perms["can_pin"],
            default_can_delete_others=default_perms["can_delete_others"],
        )
        chat.id = await self.create(payload=chat)

        # Создатель - админ
        await self._add_user_member(chat.id, creator.id, CREATOR_PERMISSIONS)

        # Остальные участники с правами по умолчанию
        for uid in member_ids:
            if uid != creator.id:
                await self._add_user_member(chat.id, uid, default_perms)

        return chat

    @hybridmethod
    async def create_partner_chat(
        self, user_id: int, partner_id: int, chat_name: str | None = None
    ):
        """
        Создать или найти существующий чат с партнёром.

        Args:
            user_id: ID пользователя (оператора)
            partner_id: ID партнёра
            chat_name: Название чата (по умолчанию имя партнёра)
        """
        # Ищем существующий чат с этим партнёром
        existing = await self._find_partner_chat(user_id, partner_id)
        if existing:
            return existing

        user = env.models.user(id=user_id)
        partner = env.models.partner(id=partner_id)

        default_perms = DEFAULT_PERMISSIONS["direct"]

        now = datetime.now(timezone.utc)
        chat = Chat(
            name=chat_name or partner.name,
            chat_type="direct",
            is_internal=False,  # Внешний чат с партнёром
            create_user_id=user,
            create_datetime=now,
            update_datetime=now,
            default_can_read=default_perms["can_read"],
            default_can_write=default_perms["can_write"],
            default_can_invite=default_perms["can_invite"],
            default_can_pin=default_perms["can_pin"],
            default_can_delete_others=default_perms["can_delete_others"],
        )
        chat.id = await self.create(payload=chat)

        # Добавляем пользователя как участника
        await self._add_user_member(chat.id, user_id, default_perms)

        # Добавляем партнёра как участника
        await self._add_partner_member(chat.id, partner_id, default_perms)

        return chat

    async def _find_partner_chat(
        self, user_id: int, partner_id: int
    ) -> "Chat | None":
        """Найти существующий чат между пользователем и партнёром."""
        session = self._get_db_session()
        query = """
            SELECT c.id FROM chat c
            JOIN chat_member cm1 ON c.id = cm1.chat_id
                AND cm1.user_id = %s AND cm1.is_active = true
            JOIN chat_member cm2 ON c.id = cm2.chat_id
                AND cm2.partner_id = %s AND cm2.is_active = true
            WHERE c.chat_type = 'direct' AND c.active = true AND c.is_internal = false
            LIMIT 1
        """
        result = await session.execute(query, (user_id, partner_id))
        if result:
            return await self.get(result[0]["id"])
        return None

    @hybridmethod
    async def create_channel(
        self,
        name: str,
        creator_id: int,
        is_public: bool = False,
        description: str | None = None,
    ):
        """Создать канал."""
        creator = env.models.user(id=creator_id)

        default_perms = DEFAULT_PERMISSIONS["channel"]

        now = datetime.now(timezone.utc)
        chat = Chat(
            name=name,
            description=description,
            chat_type="channel",
            is_public=is_public,
            create_user_id=creator,
            create_datetime=now,
            update_datetime=now,
            # В канале по умолчанию только чтение
            default_can_read=default_perms["can_read"],
            default_can_write=default_perms["can_write"],
            default_can_invite=default_perms["can_invite"],
            default_can_pin=default_perms["can_pin"],
            default_can_delete_others=default_perms["can_delete_others"],
        )
        chat.id = await self.create(payload=chat)

        # Создатель - админ канала
        await self._add_user_member(chat.id, creator_id, CREATOR_PERMISSIONS)

        return chat

    @hybridmethod
    async def get_or_create_record_chat(
        self,
        res_model: str,
        res_id: int,
        user_id: int,
    ) -> "Chat":
        """
        Получить или создать чат для записи (lazy creation).

        Если чат для записи уже существует — возвращает его и подписывает
        пользователя если он ещё не мембер.
        Если нет — создаёт новый record-чат с пользователем как первым мембером.

        Защита от race condition: pg_advisory_xact_lock внутри транзакции
        блокирует по логическому ключу до commit/rollback.
        """
        find_query = """
            SELECT id, name FROM chat
            WHERE res_model = %s AND res_id = %s
              AND chat_type = 'record' AND active = true
            LIMIT 1
        """

        # Fast path (99% случаев) — чат уже существует, без lock
        session = self._get_db_session()
        result = await session.execute(find_query, (res_model, res_id))

        if result:
            chat = Chat(id=result[0]["id"], name=result[0]["name"])
            await self._ensure_membership(chat.id, user_id)
            return chat

        # Slow path — чат не найден, берём lock и создаём
        # с защитой от дублей, так как чат создается лениво.
        async with env.apps.db.get_transaction() as session:
            await session.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s), %s)",
                (f"chat:{res_model}", res_id),
            )

            # Повторная проверка под lock (мог создаться пока ждали)
            result = await session.execute(find_query, (res_model, res_id))

            if result:
                chat = Chat(id=result[0]["id"], name=result[0]["name"])
                await self._ensure_membership(chat.id, user_id)
                return chat

            # Создаём новый record-чат
            user = env.models.user(id=user_id)
            default_perms = DEFAULT_PERMISSIONS["record"]

            now = datetime.now(timezone.utc)
            chat = Chat(
                name=f"{res_model}:{res_id}",
                chat_type="record",
                is_internal=True,
                res_model=res_model,
                res_id=res_id,
                create_user_id=user,
                create_datetime=now,
                update_datetime=now,
                default_can_read=default_perms["can_read"],
                default_can_write=default_perms["can_write"],
                default_can_invite=default_perms["can_invite"],
                default_can_pin=default_perms["can_pin"],
                default_can_delete_others=default_perms["can_delete_others"],
            )
            chat.id = await self.create(payload=chat)

            # Первый пользователь — мембер с правами record
            await self._add_user_member(chat.id, user_id, default_perms)

        # Уведомляем пользователя о новом чате через WS (вне транзакции)
        try:
            await env.apps.chat.chat_manager.notify_new_chat(user_id, chat.id)
        except Exception as e:
            logger.warning("Failed to send a websocket message: %s", e)

        return chat

    @hybridmethod
    async def find_partner_group_chat(self, partner_id: int) -> "Chat | None":
        """ЕДИНСТВЕННЫЙ внешний ГРУППОВОЙ чат партнёра (модель 1:1). Без
        создания — для открытия панели (не плодим пустой чат на просмотр).
        Если чата нет — панель предлагает кнопку «Создать чат». При нескольких
        берём самый свежий по последнему сообщению."""
        session = self._get_db_session()
        rows = await session.execute(
            """
            SELECT c.id, c.name FROM chat c
            JOIN chat_member cm ON cm.chat_id = c.id
                AND cm.partner_id = %s AND cm.is_active = true
            WHERE c.chat_type = 'group'
              AND c.is_internal = false AND c.active = true
            ORDER BY c.last_message_date DESC NULLS LAST, c.id DESC
            LIMIT 1
            """,
            (partner_id,),
        )
        if rows:
            return Chat(id=rows[0]["id"], name=rows[0]["name"])
        return None

    @hybridmethod
    async def get_or_create_partner_chat(
        self, partner_id: int, connector=None, partner_name: str | None = None
    ) -> "Chat":
        """Найти-или-создать ЕДИНСТВЕННЫЙ внешний групповой чат партнёра (1:1).

        advisory-lock по партнёру защищает от гонки (два первых сообщения /
        первый ответ одновременно). connector (опц.) даёт team_id и manager_ids
        новому чату: команда — ось team-scoped доступа, руководители —
        участники по умолчанию. Уведомление руководителей — вне транзакции.
        """
        from backend.base.crm.users.models.users import SYSTEM_USER_ID

        existing = await self.find_partner_group_chat(partner_id)
        if existing:
            return existing

        managers: list = []
        async with env.apps.db.get_transaction() as session:
            await session.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s), %s)",
                ("chat:partner", partner_id),
            )
            # re-check под локом
            existing = await self.find_partner_group_chat(partner_id)
            if existing:
                return existing

            team = None
            if connector is not None:
                conn = await env.models.chat_connector.search_one(
                    filter=[("id", "=", connector.id)],
                    fields=["id", "manager_ids", "team_id"],
                )
                if conn:
                    managers = conn.manager_ids or []
                    team = conn.team_id

            # Имя чата = имя партнёра (не "partner:id"). Если вызывающий не
            # передал имя (кнопка «Создать чат» из формы вызывает без
            # partner_name) — берём из БД.
            if not partner_name:
                partner = await env.models.partner.search_one(
                    filter=[("id", "=", partner_id)],
                    fields=["id", "name"],
                )
                if partner:
                    partner_name = partner.name

            default_perms = DEFAULT_PERMISSIONS["group"]
            now = datetime.now(timezone.utc)
            chat = Chat(
                name=partner_name or f"partner:{partner_id}",
                chat_type="group",
                is_internal=False,
                team_id=team,
                create_user_id=env.models.user(id=SYSTEM_USER_ID),
                create_datetime=now,
                update_datetime=now,
                default_can_read=default_perms["can_read"],
                default_can_write=default_perms["can_write"],
                default_can_invite=default_perms["can_invite"],
                default_can_pin=default_perms["can_pin"],
                default_can_delete_others=default_perms["can_delete_others"],
            )
            chat.id = await self.create(payload=chat)
            await self._add_partner_member(chat.id, partner_id, default_perms)
            for m in managers or []:
                uid = m.id
                if uid:
                    await self._add_user_member(chat.id, uid, default_perms)

        # Подписываем руководителей на WS (вне транзакции) — чтобы новый чат
        # прилетал вживую (иначе виден только после рефреша).
        for m in managers or []:
            uid = m.id
            if uid:
                try:
                    await env.apps.chat.chat_manager.notify_new_chat(
                        uid, chat.id
                    )
                except Exception as e:
                    logger.warning("notify_new_chat failed: %s", e)

        return chat

    async def _ensure_membership(self, chat_id: int, user_id: int):
        """Подписать пользователя на чат если ещё не мембер."""
        membership = await env.models.chat_member.get_membership(
            chat_id, user_id
        )
        if not membership:
            default_perms = DEFAULT_PERMISSIONS["record"]
            await self._add_user_member(chat_id, user_id, default_perms)

    async def _add_user_member(
        self, chat_id: int, user_id: int, permissions: dict | None = None
    ):
        """Добавить пользователя как участника чата с правами."""
        chat = env.models.chat(id=chat_id)
        user = env.models.user(id=user_id)

        # Если права не указаны, используем права чата по умолчанию
        if permissions is None:
            permissions = chat.get_default_permissions()

        member = env.models.chat_member(
            chat_id=chat,
            user_id=user,
            can_read=permissions.get("can_read", True),
            can_write=permissions.get("can_write", True),
            can_invite=permissions.get("can_invite", False),
            can_pin=permissions.get("can_pin", False),
            can_delete_others=permissions.get("can_delete_others", False),
            is_admin=permissions.get("is_admin", False),
        )
        await env.models.chat_member.create(payload=member)

    async def _add_partner_member(
        self, chat_id: int, partner_id: int, permissions: dict | None = None
    ):
        """Добавить партнёра как участника чата."""
        chat = env.models.chat(id=chat_id)
        partner = env.models.partner(id=partner_id)

        if permissions is None:
            permissions = chat.get_default_permissions()

        member = env.models.chat_member(
            chat_id=chat,
            partner_id=partner,
            can_read=permissions.get("can_read", True),
            can_write=permissions.get("can_write", True),
            can_invite=permissions.get("can_invite", False),
            can_pin=permissions.get("can_pin", False),
            can_delete_others=permissions.get("can_delete_others", False),
            is_admin=permissions.get("is_admin", False),
        )
        await env.models.chat_member.create(payload=member)

    async def add_member(
        self, user_id: int, permissions: dict | None = None
    ) -> bool:
        """Добавить участника в чат."""
        await self._add_user_member(self.id, user_id, permissions)
        return True

    async def add_partner(
        self, partner_id: int, permissions: dict | None = None
    ) -> bool:
        """Добавить партнёра в чат."""
        await self._add_partner_member(self.id, partner_id, permissions)
        return True

    async def remove_member(self, user_id: int) -> bool:
        """Удалить участника из чата (мягкое удаление)."""
        member = await env.models.chat_member.search_one(
            filter=[
                ("chat_id", "=", self.id),
                ("user_id", "=", user_id),
                ("is_active", "=", True),
            ],
        )
        if member:
            now = datetime.now(timezone.utc)
            await member.update(
                env.models.chat_member(is_active=False, left_at=now)
            )
            return True
        return False

    # async def remove_partner(self, partner_id: int) -> bool:
    #     """Удалить партнёра из чата (мягкое удаление)."""
    #     members = await env.models.chat_member.search(
    #         filter=[
    #             ("chat_id", "=", self.id),
    #             ("partner_id", "=", partner_id),
    #             ("is_active", "=", True),
    #         ],
    #         limit=1,
    #     )
    #     if members:
    #         member = members[0]
    #         now = datetime.now(timezone.utc)
    #         await member.update(
    #             env.models.chat_member(is_active=False, left_at=now)
    #         )
    #         return True
    #     return False

    async def update_last_message_date(self):
        """Обновить дату последнего сообщения."""
        now = datetime.now(timezone.utc)
        await self.update(Chat(last_message_date=now, update_datetime=now))

    async def reactivate(self) -> bool:
        """Вернуть мягко удалённый чат (active=false в true) при новом событии."""

        if self.active:
            return True

        await self.update(env.models.chat(active=True))
        session = self._get_db_session()

        # параллельную рассылку с глушением одиночных сбоёв
        member_rows = await session.execute(
            "SELECT user_id FROM chat_member "
            "WHERE chat_id = %s AND user_id IS NOT NULL AND is_active = true",
            (self.id,),
        )
        await env.apps.chat.chat_manager.notify_new_chat_bulk(
            [r["user_id"] for r in member_rows], self.id
        )
        return True

    async def get_available_connectors(
        self, current_user_id: int | None = None
    ):
        """
        Получить список доступных коннекторов для чата.

        Логика: смотрим контакты собеседника-участника чата и находим
        подходящие коннекторы по маппингу contact_type → connector_type.

        Собеседником может быть как партнёр (cm.partner_id → contact.partner_id),
        так и пользователь (cm.user_id → contact.user_id) — например, во
        внутреннем чате с другим сотрудником. Поэтому подбор идёт по обеим
        связям. current_user_id исключает контакты САМОГО отправителя, чтобы
        в direct-чате из двух юзеров не предлагать «написать самому себе».

        Args:
            current_user_id: ID текущего пользователя — его user-контакты
                из подбора исключаются. Если None — не исключаем никого.
        """
        connectors = [
            {
                "connector_id": None,
                "connector_type": "internal",
                "connector_name": "Internal",
            }
        ]

        session = env.apps.db.get_session()
        # Подбор contact → connector: тот же тип ИЛИ оба телефонного
        # формата (ContactType.MATCH_SQL) — даёт «отправку по номеру».
        # Контакт участника ищем и среди partner-, и среди user-контактов.
        # %s: current_user_id (дважды — NULL-safe исключение себя), chat_id.
        # ::int у первого параметра обязателен: в выражении `$1 IS NULL`
        # Postgres не может вывести тип параметра (IS NULL принимает любой)
        # и падает с IndeterminateDatatypeError — явный каст это чинит.
        query = f"""
            SELECT DISTINCT
                cc.id as connector_id,
                cc.type as connector_type,
                cc.name as connector_name
            FROM chat_member cm
            JOIN contact c ON c.active = true AND (
                    (cm.partner_id IS NOT NULL AND c.partner_id = cm.partner_id)
                 OR (cm.user_id IS NOT NULL AND c.user_id = cm.user_id
                        AND (%s::int IS NULL OR cm.user_id <> %s)
                        AND NOT EXISTS (
                            SELECT 1 FROM chat_member pm
                            WHERE pm.chat_id = cm.chat_id
                              AND pm.partner_id IS NOT NULL
                              AND pm.is_active = true
                        ))
                )
            JOIN contact_type ict ON ict.id = c.contact_type_id
            JOIN chat_connector cc ON cc.active = true
            JOIN contact_type cct ON cct.id = cc.contact_type_id
                AND {env.models.contact_type.MATCH_SQL}
            WHERE cm.chat_id = %s
                AND (cm.partner_id IS NOT NULL OR cm.user_id IS NOT NULL)
                AND cm.is_active = true
            ORDER BY cc.type, cc.name
        """
        result = await session.execute(
            query, (current_user_id, current_user_id, self.id)
        )
        for row in result:
            connectors.append(
                {
                    "connector_id": row["connector_id"],
                    "connector_type": row["connector_type"],
                    "connector_name": row["connector_name"],
                }
            )

        return connectors
