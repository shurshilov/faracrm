# Copyright 2025 FARA CRM
# Chat module - main chat/channel model

import asyncio
from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING

from starlette.status import HTTP_403_FORBIDDEN

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
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.crm.users.audit_mixin import AuditMixin
from backend.base.crm.chat.models.chat_member import (
    ADMIN,
    DIRECT,
    MEMBER,
    ChatPermissions,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_message import ChatMessage
    from backend.base.crm.chat.models.chat_member import ChatMember
    from backend.base.crm.chat.models.chat_external_chat import (
        ChatExternalChat,
    )
    from backend.base.crm.leads.models.team_crm import TeamCrm
    from backend.base.crm.users.models.users import User
    from backend.project_setup import ChatConnector


# Контакты собеседников чата — общая часть подбора коннекторов и получателей.
# Собеседник — партнёр-участник (contact.partner_id) или пользователь
# (contact.user_id), например во внутреннем чате с сотрудником. Пользователей
# берём, только когда в чате нет партнёров: иначе в клиентском чате оператор
# со своим контактом того же типа попал бы в получатели. Самого отправителя
# исключаем. Первые два %s — id отправителя (::int обязателен: в `$1 IS NULL`
# Postgres не выводит тип параметра), дальше — параметры вызывающего.
_MEMBER_CONTACTS_SQL = """
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
"""


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

    # Полиморфный ребёнок: record-чат «Заметки» записи. Каждая модель
    # получает поле-связь note_chat_ids (0 или 1 чат) автоматически — см.
    # ModelsCore._attach_polymorphic_fields. Каскад при удалении записи —
    # тем же реестром (PolymorphicParentMixin).
    __polymorphic_field__ = (
        "note_chat_ids",
        [("chat_type", "=", "record"), ("active", "=", True)],
    )

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
    # default_db: на старой базе колонка появляется сразу с false у всех.
    default_can_remove: bool = Boolean(
        default=False,
        default_db=True,
        description="Право удаления участников по умолчанию",
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

    def get_default_permissions(self) -> ChatPermissions:
        """Права нового участника этого чата (default_can_*)."""
        return ChatPermissions(
            can_read=self.default_can_read,
            can_write=self.default_can_write,
            can_invite=self.default_can_invite,
            can_remove=self.default_can_remove,
            can_pin=self.default_can_pin,
            can_delete_others=self.default_can_delete_others,
        )

    def display_name(self, members: list[dict], current_user_id: int) -> str:
        """Имя чата для клиента.

        Для direct-чата — имя собеседника:
          - имя всегда актуально, если собеседник сменил имя;
          - старые чаты «переименовываются» сами собой — имя не зависит от
            того, когда и под каким названием чат был создан;
          - имя корректно для каждого зрителя (A видит B, B видит A) — одного
            хранимого поля для этого в принципе не хватило бы.
        """
        if self.chat_type != "direct":
            return self.name
        # Собеседник = любой участник, кроме текущего юзера. Партнёр
        # (member_type 'partner') никогда не является текущим юзером, поэтому
        # исключаем только user-участника с совпадающим id.
        others = [
            m
            for m in members
            if not (m["member_type"] == "user" and m["id"] == current_user_id)
        ]
        if not others:
            return self.name  # чат с самим собой / собеседник не найден
        return others[0]["name"] or self.name

    @hybridmethod
    async def check_read_access(self, chat_id: int) -> None:
        """Чат читают его участники, команда чата и суперпользователь — это
        решают правила доступа модели chat. Остальным 403."""
        if not await self.exists(filter=[("id", "=", chat_id)]):
            raise FaraException(
                {"content": "ACCESS_DENIED", "status_code": HTTP_403_FORBIDDEN}
            )

    @hybridmethod
    async def create_direct_chat(self, user1_id: int, user2_id: int):
        """
        Создать или найти существующий прямой чат между двумя пользователями.
        """
        # Ищем существующий прямой чат между этими пользователями
        existing = await self._find_direct_chat(user1_id, user2_id)
        if existing:
            return existing

        # TODO: gather
        user1 = await env.models.user.get(user1_id)
        user2 = await env.models.user.get(user2_id)

        chat = Chat(
            name=f"{user2.name}", chat_type="direct", create_user_id=user1
        )
        chat.id = await self.create(payload=chat)

        # В direct чате оба пользователя имеют одинаковые права
        await self._add_user_member(chat.id, user1_id, DIRECT)
        await self._add_user_member(chat.id, user2_id, DIRECT)

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
        chat = Chat(
            name=name,
            chat_type="group",
            create_user_id=env.models.user(id=creator_id),
        )
        chat.id = await self.create(payload=chat)

        # Создатель - админ
        await self._add_user_member(chat.id, creator_id, ADMIN)

        # Остальные участники с правами по умолчанию
        for uid in member_ids:
            if uid != creator_id:
                await self._add_user_member(chat.id, uid, MEMBER)

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

        Заметки записи доступны тому, кто видит саму запись: это решают
        правила доступа её модели (res_model — имя таблицы).

        Защита от race condition: pg_advisory_xact_lock внутри транзакции
        блокирует по логическому ключу до commit/rollback.
        """
        try:
            Model = env.models._get_model_class_by_table(res_model)
        except KeyError:
            Model = None
        if Model is None or not await Model.exists(
            filter=[("id", "=", res_id)]
        ):
            raise FaraException(
                {"content": "ACCESS_DENIED", "status_code": HTTP_403_FORBIDDEN}
            )

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
            chat = Chat(
                name=f"{res_model}:{res_id}",
                chat_type="record",
                res_model=res_model,
                res_id=res_id,
                create_user_id=env.models.user(id=user_id),
            )
            chat.id = await self.create(payload=chat)

            # Первый пользователь — мембер с правами record
            await self._add_user_member(chat.id, user_id, MEMBER)

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

            chat = Chat(
                name=partner_name or f"partner:{partner_id}",
                chat_type="group",
                is_internal=False,
                team_id=team,
                create_user_id=env.models.user(id=SYSTEM_USER_ID),
            )
            chat.id = await self.create(payload=chat)
            await env.models.chat_member.add(
                chat.id, MEMBER, partner_id=partner_id
            )
            for m in managers or []:
                uid = m.id
                if uid:
                    await self._add_user_member(chat.id, uid, MEMBER)

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
            await self._add_user_member(chat_id, user_id, MEMBER)

    async def _add_user_member(
        self, chat_id: int, user_id: int, permissions: ChatPermissions
    ):
        """Добавить пользователя в чат с правами.

        В группе без админа он становится админом: чат клиента создаёт
        система, и админом будет первый пользователь — руководитель
        коннектора, взявший лид, нажавший «Создать чат».
        """
        if not permissions.is_admin:
            # sudo: вступающий в чат его ещё не видит
            chat = await env.models.chat.sudo().get(
                chat_id, fields=["id", "chat_type"]
            )
            if (
                chat.chat_type == "group"
                and await env.models.chat_member.count_admins(chat_id) == 0
            ):
                permissions = ADMIN

        await env.models.chat_member.add(chat_id, permissions, user_id=user_id)

    async def add_member(self, user_id: int) -> bool:
        """Добавить участника с правами чата по умолчанию. self — загруженный
        чат, а не заглушка с id: права берутся из его default_can_*."""
        await self._add_user_member(
            self.id, user_id, self.get_default_permissions()
        )
        return True

    async def add_partner(self, partner_id: int) -> bool:
        """Добавить партнёра (права — как у add_member)."""
        await env.models.chat_member.add(
            self.id, self.get_default_permissions(), partner_id=partner_id
        )
        return True

    async def remove_member(self, user_id: int) -> bool:
        """Удалить участника из чата (мягкое удаление)."""
        return await env.models.chat_member.remove(self.id, user_id)

    async def update_last_message_date(self):
        """Обновить дату последнего сообщения."""
        now = datetime.now(timezone.utc)
        await self.update(Chat(last_message_date=now, update_datetime=now))

    async def reactivate(self) -> bool:
        """Вернуть мягко удалённый чат (active=false в true) при новом событии."""

        if self.active:
            return True

        await self.update(env.models.chat(active=True))
        # параллельную рассылку с глушением одиночных сбоёв
        await env.apps.chat.chat_manager.notify_new_chat_bulk(
            await env.models.chat_member.active_user_ids(self.id), self.id
        )
        return True

    async def get_available_connectors(
        self, current_user_id: int | None = None
    ):
        """
        Получить список доступных коннекторов для чата.

        Логика: смотрим контакты собеседника-участника чата и находим
        подходящие коннекторы по маппингу contact_type → connector_type:
        тот же тип ИЛИ оба телефонного формата (ContactType.MATCH_SQL) — это
        даёт «отправку по номеру». Чьи контакты берутся — см.
        _MEMBER_CONTACTS_SQL.

        Коннекторы уведомлений (category = notification, например Web Push)
        — не канал переписки и в список не попадают: пуши рассылает сервис
        уведомлений (notify_on_new_message), а не выбор канала.

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

        result = await self._get_db_session().execute(
            f"""
            SELECT DISTINCT
                cc.id as connector_id,
                cc.type as connector_type,
                cc.name as connector_name
            {_MEMBER_CONTACTS_SQL}
            JOIN chat_connector cc ON cc.active = true
                AND cc.category IS DISTINCT FROM 'notification'
            JOIN contact_type cct ON cct.id = cc.contact_type_id
                AND {env.models.contact_type.MATCH_SQL}
            WHERE cm.chat_id = %s
                AND (cm.partner_id IS NOT NULL OR cm.user_id IS NOT NULL)
                AND cm.is_active = true
            ORDER BY cc.type, cc.name
            """,
            (current_user_id, current_user_id, self.id),
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

    async def get_recipients(
        self, connector: "ChatConnector", current_user_id: int
    ) -> list[dict]:
        """Контакты собеседников, на которые коннектор отправит сообщение:
        [{"id", "contact_value"}].

        Подходит контакт типа коннектора ИЛИ оба телефонного формата
        (ContactType.MATCH_SQL). Есть контакт точно нужного типа — шлём только
        по нему; phone-format фолбэк идёт в ход, лишь когда точного нет (иначе
        рискуем отправить на второй, посторонний номер партнёра).
        """
        if not connector.contact_type_id:
            return []

        rows = await self._get_db_session().execute(
            f"""
            SELECT c.id, c.name as contact_value,
                   (cct.id = ict.id) as is_exact
            {_MEMBER_CONTACTS_SQL}
            JOIN contact_type cct ON cct.id = %s
                AND {env.models.contact_type.MATCH_SQL}
            WHERE cm.chat_id = %s
              AND (cm.partner_id IS NOT NULL OR cm.user_id IS NOT NULL)
              AND cm.is_active = true
            """,
            (
                current_user_id,
                current_user_id,
                connector.contact_type_id.id,
                self.id,
            ),
        )
        rows = list(rows)
        if any(row["is_exact"] for row in rows):
            rows = [row for row in rows if row["is_exact"]]
        return [
            {"id": row["id"], "contact_value": row["contact_value"]}
            for row in rows
        ]

    @hybridmethod
    async def list_for_user(
        self,
        user: "User",
        *,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        is_internal: bool | None = None,
        chat_type: str | None = None,
        connector_type: str | None = None,
        folder_id: int | None = None,
        include_deleted: bool = False,
        include_record: bool = False,
        include_foreign: bool = False,
        scope: str | None = None,
    ) -> list[dict]:
        """Чаты пользователя для списка (GET /chats): с участниками, последним
        сообщением, непрочитанными и закрепом. Что попадает в список — см.
        _search_ids_for_user."""
        rows = await self._search_ids_for_user(
            user,
            limit=limit,
            offset=offset,
            search=search,
            is_internal=is_internal,
            chat_type=chat_type,
            connector_type=connector_type,
            folder_id=folder_id,
            include_deleted=include_deleted,
            include_record=include_record,
            include_foreign=include_foreign,
            scope=scope,
        )
        if not rows:
            return []

        chat_ids = [row["id"] for row in rows]
        # В foreign-режиме поля is_pinned нет — закрепа нет.
        pinned = {row["id"]: bool(row.get("is_pinned")) for row in rows}

        # Параллельно: вне транзакции каждый запрос идёт своим соединением.
        chats, members, last_messages, unread_rows = await asyncio.gather(
            self.search(
                filter=[("id", "in", chat_ids)],
                fields=[
                    "id",
                    "name",
                    "chat_type",
                    "is_internal",
                    "last_message_date",
                    "create_datetime",
                    "active",
                ],
                limit=limit,
            ),
            env.models.chat_member.list_for_chats(chat_ids),
            env.models.chat_message.last_by_chat(chat_ids),
            env.models.chat_message.unread_counts(user.id, chat_ids),
        )
        unread = {row["chat_id"]: row["unread_count"] for row in unread_rows}

        result = []
        for chat in chats:
            chat_members = members.get(chat.id, [])
            result.append(
                {
                    "id": chat.id,
                    "name": chat.display_name(chat_members, user.id),
                    "chat_type": chat.chat_type,
                    "is_internal": chat.is_internal,
                    "active": chat.active,
                    # Всегда []: поле фронтом не читается, но тип
                    # Chat.connectors там не опционален. Живой пикер —
                    # GET /chats/{id}/connectors.
                    "connectors": [],
                    "last_message_date": (
                        chat.last_message_date.isoformat()
                        if chat.last_message_date
                        else None
                    ),
                    "create_datetime": (
                        chat.create_datetime.isoformat()
                        if chat.create_datetime
                        else None
                    ),
                    "unread_count": unread.get(chat.id, 0),
                    "members": chat_members,
                    "is_pinned": pinned.get(chat.id, False),
                    "last_message": last_messages.get(chat.id),
                }
            )

        # Закреплённые сверху, затем по дате последнего сообщения.
        return sorted(
            result,
            key=lambda x: (
                1 if x["is_pinned"] else 0,
                x["last_message_date"] or x["create_datetime"] or "",
            ),
            reverse=True,
        )

    async def _search_ids_for_user(
        self,
        user: "User",
        *,
        limit: int,
        offset: int,
        search: str | None,
        is_internal: bool | None,
        chat_type: str | None,
        connector_type: str | None,
        folder_id: int | None,
        include_deleted: bool,
        include_record: bool,
        include_foreign: bool,
        scope: str | None,
    ) -> list[dict]:
        """Страница списка чатов: строки {id, last_message_date, is_pinned}.

        По умолчанию пользователь (в т.ч. админ) видит только свои активные
        чаты, не являющиеся record-чатами:
          - chat_member.user_id = me AND chat_member.is_active = true
          - chat.active = true
          - chat.chat_type != 'record'

        Флаги снимают отдельные ограничения:
          - include_deleted  → снимает фильтр по chat.active
          - include_record   → показывает record-чаты
          - include_foreign  → снимает требование членства (только
            суперпользователь — проверяет вызывающий)

        Комбо-фильтрация:
        - is_internal=True + chat_type=direct → Внутренние личные
        - is_internal=True + chat_type=group  → Внутренние группы
        - is_internal=False + connector_type=telegram → Telegram чаты
        """
        session = self._get_db_session()
        # Команды пользователя — уже в сессии (гидрируются при сборке).
        my_team_ids = [t.id for t in (user.team_ids or [])]

        # Папку грузим РАНО: её kind влияет на базовый JOIN. Внешние папки
        # external_mine/external_all — глобальные, резолвятся по kind (не
        # доменом, как папки коннекторов): членство/team не выразить доменом
        # над chat. external_all = team-видимость (LEFT JOIN, членство
        # необязательно).
        folder_row = None
        if folder_id is not None:
            folder_row = await env.models.chat_folder.search_one(
                filter=[("id", "=", folder_id)],
                fields=["id", "domain", "connector_id", "kind"],
            )
            if not folder_row:
                return []
        folder_kind = folder_row.kind if folder_row else None

        # «Все» (внешние, team-scoped): из scope=all ИЛИ папки external_all.
        want_all = (scope == "all") or (folder_kind == "external_all")

        # Строим SQL динамически. Плейсхолдеры FROM/JOIN (join_params) держим
        # ОТДЕЛЬНО от WHERE (where_params): в итоговом тексте все JOIN-%s идут
        # раньше WHERE-%s, поэтому итоговый порядок = join_params + where_params.
        join_params: list = []
        conditions: list[str] = []
        where_params: list = []

        if include_foreign:
            base_query = """
                SELECT DISTINCT c.id, c.last_message_date
                FROM chat c
            """
        else:
            # LEFT JOIN + cm.user_id в ON: членство не обязательно, чтобы
            # scope=all мог показать team-scoped внешние чаты, где юзер НЕ
            # участник.
            base_query = """
                SELECT DISTINCT c.id, c.last_message_date, cm.is_pinned
                FROM chat c
                LEFT JOIN chat_member cm
                    ON c.id = cm.chat_id
                   AND cm.is_active = true
                   AND cm.user_id = %s
            """
            join_params.append(user.id)
            if want_all and my_team_ids:
                # Мои чаты (участник) ИЛИ чаты моих команд (team-scoped).
                conditions.append(
                    "(cm.user_id IS NOT NULL OR c.team_id = ANY(%s))"
                )
                where_params.append(my_team_ids)
            else:
                # 'mine' (дефолт) — только где я активный участник.
                conditions.append("cm.user_id IS NOT NULL")

        # Soft-delete: фильтр по active снимается флагом (доступно всем)
        if not include_deleted:
            conditions.append("c.active = true")

        # Record-чаты: по умолчанию исключены
        if not include_record:
            conditions.append("c.chat_type != 'record'")

        # Поиск по имени чата ИЛИ участника: у direct-чатов отображаемое имя —
        # собеседник, у внешних — партнёр, поэтому одного c.name мало. Фильтр
        # на бэке: раньше фронт фильтровал по имени только среди первых 100
        # загруженных чатов (issue #28).
        if search and search.strip():
            # Экранирование LIKE — у диалекта (одна точка для всех поисков).
            pattern = "%" + self._dialect.like_escape(search.strip()) + "%"
            conditions.append("""(c.name ILIKE %s OR EXISTS (
                    SELECT 1 FROM chat_member sm
                    LEFT JOIN users su ON su.id = sm.user_id
                    LEFT JOIN partners sp ON sp.id = sm.partner_id
                    WHERE sm.chat_id = c.id AND sm.is_active = true
                      AND (su.name ILIKE %s OR sp.name ILIKE %s)
                ))""")
            where_params.extend([pattern, pattern, pattern])

        # Фильтр is_internal
        if is_internal is True:
            conditions.append("c.is_internal = true")
        elif is_internal is False:
            conditions.append("c.is_internal = false")

        # Фильтр chat_type
        if chat_type:
            if chat_type == "group":
                conditions.append("c.chat_type IN ('group', 'channel')")
            else:
                conditions.append("c.chat_type = %s")
                where_params.append(chat_type)

        # Фильтр connector_type — через контакты партнёров-участников чата.
        # Логика: connector.contact_type_id → contact.contact_type_id → partner
        # → chat_member. Ищем чаты где у партнёра есть контакт с тем же
        # contact_type_id что у коннектора.
        if connector_type:
            contact_type = await env.models.contact_type.get_contact_type_id_for_connector(
                connector_type
            )
            if contact_type:
                base_query += """
                JOIN chat_member cm_filter ON c.id = cm_filter.chat_id
                    AND cm_filter.partner_id IS NOT NULL
                    AND cm_filter.is_active = true
                JOIN contact contact_filter
                    ON contact_filter.partner_id = cm_filter.partner_id
                    AND contact_filter.active = true
                    AND contact_filter.contact_type_id = %s
                """
                # JOIN-плейсхолдер (текстово после cm-LEFT-JOIN).
                join_params.append(contact_type.id)

        # Резолвинг папки. Три ветки:
        #   - external_mine/external_all → по kind: только внешние чаты
        #     (team-vs-membership уже задан базовым условием want_all выше);
        #   - папка коннектора → по chat_external_chat (не domain);
        #   - остальные → штатным ORM-поиском по domain (правила chat_folder
        #     уже ограничили выборку своими+глобальными папками).
        if folder_row is not None:
            if folder_kind in ("external_mine", "external_all"):
                conditions.append("c.is_internal = false")
            elif folder_row.connector_id:
                ext_rows = await session.execute(
                    "SELECT DISTINCT chat_id FROM chat_external_chat "
                    "WHERE connector_id = %s",
                    (folder_row.connector_id.id,),
                )
                ext_ids = [r["chat_id"] for r in ext_rows]
                if not ext_ids:
                    return []
                conditions.append("c.id = ANY(%s)")
                where_params.append(ext_ids)
            else:
                domain = folder_row.domain or []
                if domain:
                    matched = await self.search(
                        filter=domain, fields=["id"], limit=10000
                    )
                    matched_ids = [m.id for m in matched]
                    if not matched_ids:
                        return []
                    conditions.append("c.id = ANY(%s)")
                    where_params.append(matched_ids)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        # Закреплённые чаты сверху. В foreign-режиме нет cm-джойна → без
        # закрепа. LEFT JOIN даёт cm.is_pinned=NULL у team-чатов, где юзер НЕ
        # участник. NULLS LAST кладёт их вниз (по умолчанию DESC = NULLS
        # FIRST). Сортируем именно по cm.is_pinned (а не COALESCE) — оно в
        # списке SELECT DISTINCT, иначе Postgres: "ORDER BY expressions must
        # appear in select list".
        if include_foreign:
            order_by = "c.last_message_date DESC NULLS LAST"
        else:
            order_by = (
                "cm.is_pinned DESC NULLS LAST, "
                "c.last_message_date DESC NULLS LAST"
            )

        # Порядок параметров: JOIN/FROM, затем WHERE, затем LIMIT/OFFSET.
        return await session.execute(
            f"""
            {base_query}
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
            """,
            tuple(join_params + where_params + [limit, offset]),
        )
