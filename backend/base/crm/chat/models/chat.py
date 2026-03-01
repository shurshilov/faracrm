# Copyright 2025 FARA CRM
# Chat module - main chat/channel model

from datetime import datetime, timezone
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

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.chat.models.chat_message import ChatMessage
    from backend.base.crm.chat.models.chat_member import ChatMember
    from backend.base.crm.chat.models.chat_external_chat import (
        ChatExternalChat,
    )


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


class Chat(DotModel):
    """
    Chat model

    Типы чатов:
    - direct: прямой чат между двумя пользователями
    - group: групповой чат с несколькими участниками
    - channel: публичный или приватный канал
    - record: чат привязанный к сущности
    """

    __table__ = "chat"

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

    # Временные метки
    create_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc), description="Дата создания"
    )
    write_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc),
        description="Дата последнего изменения",
    )
    last_message_date: datetime | None = Datetime(
        description="Дата последнего сообщения"
    )

    # Создатель чата
    create_user_id: "User" = Many2one(
        relation_table=lambda: env.models.user, description="Создатель чата"
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
            name=f"{user1.name} - {user2.name}",
            chat_type="direct",
            create_user_id=user1,
            create_date=now,
            write_date=now,
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
            SELECT c.id FROM chat c
            JOIN chat_member cm1 ON c.id = cm1.chat_id
                AND cm1.user_id = %s AND cm1.is_active = true
            JOIN chat_member cm2 ON c.id = cm2.chat_id
                AND cm2.user_id = %s AND cm2.is_active = true
            WHERE c.chat_type = 'direct' AND c.active = true
            LIMIT 1
        """
        result = await session.execute(query, (user1_id, user2_id))
        if result:
            return await self.get(result[0]["id"])
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
            create_date=now,
            write_date=now,
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
            create_date=now,
            write_date=now,
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
        creator = await env.models.user.get(creator_id)

        default_perms = DEFAULT_PERMISSIONS["channel"]

        now = datetime.now(timezone.utc)
        chat = Chat(
            name=name,
            description=description,
            chat_type="channel",
            is_public=is_public,
            create_user_id=creator,
            create_date=now,
            write_date=now,
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

        Защита от race condition: использует SELECT ... FOR UPDATE SKIP LOCKED
        для предотвращения дублирования при параллельных запросах.
        """
        session = self._get_db_session()

        # Атомарный поиск с блокировкой
        lock_query = """
            SELECT id FROM chat
            WHERE res_model = %s AND res_id = %s
              AND chat_type = 'record' AND active = true
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """
        result = await session.execute(lock_query, (res_model, res_id))

        if result:
            chat_id = result[0]["id"]
            chat = await self.get(chat_id)

            # Подписываем пользователя если ещё не мембер
            from backend.base.crm.chat.models.chat_member import ChatMember

            membership = await ChatMember.get_membership(chat.id, user_id)
            if not membership:
                default_perms = DEFAULT_PERMISSIONS["record"]
                await self._add_user_member(chat.id, user_id, default_perms)
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
            create_date=now,
            write_date=now,
            default_can_read=default_perms["can_read"],
            default_can_write=default_perms["can_write"],
            default_can_invite=default_perms["can_invite"],
            default_can_pin=default_perms["can_pin"],
            default_can_delete_others=default_perms["can_delete_others"],
        )
        chat.id = await self.create(payload=chat)

        # Первый пользователь — мембер с правами record
        await self._add_user_member(chat.id, user_id, default_perms)

        # Уведомляем пользователя о новом чате через WS
        try:
            from backend.base.crm.chat import chat_manager

            await chat_manager.notify_new_chat(user_id, chat.id)
        except Exception:
            pass  # WS не обязателен

        return chat

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
        members = await env.models.chat_member.search(
            filter=[
                ("chat_id", "=", self.id),
                ("user_id", "=", user_id),
                ("is_active", "=", True),
            ],
            limit=1,
        )
        if members:
            member = members[0]
            now = datetime.now(timezone.utc)
            await member.update(
                env.models.chat_member(is_active=False, left_at=now)
            )
            return True
        return False

    async def remove_partner(self, partner_id: int) -> bool:
        """Удалить партнёра из чата (мягкое удаление)."""
        members = await env.models.chat_member.search(
            filter=[
                ("chat_id", "=", self.id),
                ("partner_id", "=", partner_id),
                ("is_active", "=", True),
            ],
            limit=1,
        )
        if members:
            member = members[0]
            now = datetime.now(timezone.utc)
            await member.update(
                env.models.chat_member(is_active=False, left_at=now)
            )
            return True
        return False

    async def update_last_message_date(self):
        """Обновить дату последнего сообщения."""
        now = datetime.now(timezone.utc)
        await self.update(Chat(last_message_date=now, write_date=now))

    async def get_member_permissions(self, user_id: int) -> dict | None:
        """Получить права участника в чате."""
        members = await env.models.chat_member.search(
            filter=[
                ("chat_id", "=", self.id),
                ("user_id", "=", user_id),
                ("is_active", "=", True),
            ],
            limit=1,
        )
        if members:
            return members[0].get_permissions()
        return None

    async def set_member_permissions(
        self, user_id: int, permissions: dict
    ) -> bool:
        """Установить права участника в чате."""
        members = await env.models.chat_member.search(
            filter=[
                ("chat_id", "=", self.id),
                ("user_id", "=", user_id),
                ("is_active", "=", True),
            ],
            limit=1,
        )
        if members:
            member = members[0]
            valid_perms = {
                k: v for k, v in permissions.items() if hasattr(member, k)
            }
            if valid_perms:
                await member.update(env.models.chat_member(**valid_perms))
            return True
        return False

    async def get_available_connectors(self) -> list[dict]:
        """
        Получить список доступных коннекторов для чата.

        Логика: смотрим контакты партнёра-участника чата и находим
        подходящие коннекторы по маппингу contact_type → connector_type.
        """
        connectors = [
            {
                "connector_id": None,
                "connector_type": "internal",
                "connector_name": "Internal",
            }
        ]

        if not self.is_internal:
            session = self._get_db_session()
            # Маппинг contact connector через общий contact_type_id (integer FK)
            query = """
                SELECT DISTINCT
                    cc.id as connector_id,
                    cc.type as connector_type,
                    cc.name as connector_name
                FROM chat_member cm
                JOIN contact c ON c.partner_id = cm.partner_id AND c.active = true
                JOIN chat_connector cc ON cc.active = true
                    AND cc.contact_type_id = c.contact_type_id
                WHERE cm.chat_id = %s
                  AND cm.partner_id IS NOT NULL
                  AND cm.is_active = true
                ORDER BY cc.type, cc.name
            """
            result = await session.execute(query, (self.id,))
            for row in result:
                connectors.append(
                    {
                        "connector_id": row["connector_id"],
                        "connector_type": row["connector_type"],
                        "connector_name": row["connector_name"],
                    }
                )

        return connectors
