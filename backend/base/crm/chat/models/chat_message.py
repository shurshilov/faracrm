# Copyright 2025 FARA CRM
# Chat module - message model

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING


from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Text,
    Boolean,
    Selection,
    Many2one,
    One2many,
    PolymorphicOne2many,
)
from backend.base.crm.security.polymorphic_parent import (
    PolymorphicParentMixin,
)
from backend.base.system.core.enviroment import env
from backend.base.crm.users.audit_mixin import AuditMixin

_log = logging.getLogger(__name__)

# Тело в WS-событии режем: pg_notify принимает ~8 КБ на событие, длинное
# письмо в него не влезало и раньше терялось целиком. Символов, не байт:
# кириллица в UTF-8 занимает два, запас до лимита остаётся.
WS_BODY_LIMIT = 2000

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.partners import Partner
    from backend.base.crm.leads.models.leads import Lead
    from backend.base.crm.tasks.models.task import Task
    from backend.base.crm.chat.models.chat import Chat
    from backend.project_setup import ChatConnector
    from backend.base.crm.chat.models.chat_external_message import (
        ChatExternalMessage,
    )
    from backend.base.crm.attachments.models.attachments import Attachment
    from backend.base.system.dotorm.dotorm.components.filter_parser import (
        FilterExpression,
    )


class ChatMessage(AuditMixin, PolymorphicParentMixin):
    """
    Модель сообщения чата.
    Паттерн Nullable FKs

    Поддерживает:
    - Текстовые сообщения
    - Вложения (файлы, изображения)
    - Системные уведомления
    - Связь с внешними системами (Telegram, WhatsApp и т.д.)

    Автор сообщения может быть:
    - Пользователем системы (author_user_id) - для операторов
    - Партнёром (author_partner_id) - для внешних клиентов
    """

    __table__ = "chat_message"
    # Отключаем публичные /auto/chat_message/... эндпоинты.
    __auto_crud__ = False

    # Составной индекс для самого горячего запроса в чатах:
    # выборка сообщений чата с фильтром is_deleted=false и сортировкой по id.
    # Покрывает: /chats/.../messages/unread-count, /chats/.../messages/mark-read,
    # search_count, watermark-запрос unread. id в конце даёт index-only scan
    # для ORDER BY id DESC LIMIT 1 (последнее сообщение).
    #
    # Второй индекс — под «ленту» лида: выборка сообщений по lead_id с
    # is_deleted=false и сортировкой по id DESC (keyset-пагинация). Партнёр-
    # лента ходит через chat_member(partner_id) (см. индекс там), поэтому
    # message.partner_id НЕ денормализуем.
    __indexes__ = [
        ("chat_id", "is_deleted", "id"),
        ("lead_id", "is_deleted", "id"),
        ("task_id", "is_deleted", "id"),
    ]

    id: int = Integer(primary_key=True)

    # Содержимое сообщения
    body: str | None = Text(
        description="Текст сообщения (может содержать HTML)"
    )
    subject: str | None = Char(max_length=255, description="Тема сообщения")

    # Тип сообщения
    message_type: str = Selection(
        options=[
            ("comment", "Comment"),
            ("notification", "Notification"),
            ("system", "System"),
            ("email", "Email"),
            ("call", "call"),
        ],
        default="comment",
        description="Тип: comment - обычное, notification - уведомление, system - системное",
    )

    # Связь с чатом
    chat_id: "Chat" = Many2one(
        relation_table=lambda: env.models.chat,
        description="Чат, к которому относится сообщение",
        required=True,
    )

    # Автор сообщения (пользователь системы - оператор).
    # index=True на обоих авторах: самая большая таблица, и без индекса
    # удаление пользователя/партнёра (FK ON DELETE SET NULL) — seq scan по ней.
    author_user_id: "User | None" = Many2one(
        relation_table=lambda: env.models.user,
        index=True,
        description="Автор - пользователь системы (для операторов)",
    )

    # Автор сообщения (партнёр - внешний клиент)
    author_partner_id: "Partner | None" = Many2one(
        relation_table=lambda: env.models.partner,
        index=True,
        description="Автор - партнёр (для внешних клиентов)",
    )

    # Статус
    is_deleted: bool = Boolean(
        default=False, description="Удалено (мягкое удаление)"
    )

    # Связь с внешними системами (для интеграции)
    connector_id: "ChatConnector | None" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        description="Коннектор, через который отправлено/получено сообщение",
    )

    # Денормализованный тип коннектора (email/telegram/internal/...).
    # Проставляется при создании из connector.type. По нему фронт понимает
    # канал сообщения (email → HTML-рендер) без join на коннектор и без
    # костыля «пометить message_type='email'». Null, если коннектора нет.
    connector_type: str | None = Char(
        max_length=50,
        index=True,
        description="Тип коннектора сообщения (денормализовано из "
        "connector.type)",
    )

    # Внешние сообщения (one2many связь)
    external_message_ids: list["ChatExternalMessage"] = One2many(
        store=False,
        relation_table=lambda: env.models.chat_external_message,
        relation_table_field="message_id",
        description="Связанные внешние сообщения",
    )

    # Вложения
    attachment_ids: list["Attachment"] = PolymorphicOne2many(
        store=False,
        relation_table=lambda: env.models.attachment,
        relation_table_field="res_id",
        description="Вложения к сообщению",
    )

    # Ответ на сообщение (для thread/reply функциональности)
    parent_id: "ChatMessage | None" = Many2one(
        index=True,
        relation_table=lambda: env.models.chat_message,
        description="Родительское сообщение (для ответов)",
    )

    # Лид, к которому относится сообщение — тег для «ленты».
    # Ставится синхронно при создании: входящее — лид из лидогенерации;
    # исходящее из лид-панели — сам лид. NULL = сообщение вне лида (видно
    # только в партнёр-скоупе ленты). ondelete='set null' — удаление лида не
    # рушит историю переписки, тег просто обнуляется (при merge/reassign
    # лид перетегируется, см. Lead). Партнёр НЕ денормализуем на сообщение —
    # он выводится из chat_member (единственный тег здесь — lead_id).
    lead_id: "Lead | None" = Many2one(
        index=True,
        ondelete="set null",
        relation_table=lambda: env.models.lead,
        description="Лид, к которому относится сообщение (тег ленты)",
    )

    # Второй тег «ленты» — задача. Параллельно lead_id: сообщение можно
    # привязать к лиду И/ИЛИ к задаче. Список тегов чата собирает ручка
    # GET /chats/{id}/tags (GROUP BY по обоим FK).
    task_id: "Task | None" = Many2one(
        index=True,
        ondelete="set null",
        relation_table=lambda: env.models.task,
        description="Задача, к которой относится сообщение (тег ленты)",
    )

    # Звёздочка/избранное
    starred: bool = Boolean(default=False, description="Отмечено как важное")

    # Закреплённое сообщение
    pinned: bool = Boolean(default=False, description="Закреплённое сообщение")

    # Редактировано
    is_edited: bool = Boolean(
        default=False, description="Сообщение было отредактировано"
    )

    # Сообщение сохранено, но во внешний канал (connector_id) не ушло.
    # default_db: на старой базе колонка появляется сразу с false у всех.
    send_failed: bool = Boolean(
        default=False,
        default_db=True,
        description="Не доставлено во внешний канал",
    )

    @property
    def author(self) -> dict:
        """
        Универсальный автор сообщения.
        Возвращает данные автора независимо от типа (user или partner).
        """
        if self.author_user_id:
            return {
                "id": self.author_user_id.id,
                "name": self.author_user_id.name,
                "type": "user",
            }
        if self.author_partner_id:
            return {
                "id": self.author_partner_id.id,
                "name": self.author_partner_id.name,
                "type": "partner",
            }
        return {"id": None, "name": "Unknown", "type": None}

    def serialize_for_ws(
        self, *, author: dict, attachments: list[dict], **tags
    ) -> dict:
        """Форма сообщения для WS-события `new_message` — одна для всех путей
        (исходящее, пересылка, системное, входящее).

        Совпадает с REST serialize_for_chat, чтобы фронт клал событие в тот же
        кэш без пересборки. Явно передаются: author (у только что созданной
        записи связанный пользователь несёт один id, а у входящего это
        контрагент, не автор-стаб), attachments (уже сериализованы, см.
        Attachment.serialize_for_chat) и tags — теги «ленты»
        (partner_id/lead_id/task_id и т.п.). Тело длиннее WS_BODY_LIMIT
        обрезается и помечается body_truncated: фронт дочитает его из REST.
        """
        data = self.serialize_for_chat(
            is_read=False, attachments=attachments, reactions=[]
        )
        data["author"] = author
        # Связи у свежей записи — объекты с одним id; в событие идут id.
        data["parent_id"] = getattr(self.parent_id, "id", self.parent_id)
        data["connector_id"] = getattr(
            self.connector_id, "id", self.connector_id
        )
        data.update(tags)
        body = data["body"] or ""
        if len(body) > WS_BODY_LIMIT:
            data["body"] = body[:WS_BODY_LIMIT]
            data["body_truncated"] = True
        return data

    def serialize_for_chat(
        self,
        *,
        is_read: bool,
        attachments: list[dict],
        reactions: list[dict],
    ) -> dict:
        """Форма сообщения для списка REST GET /messages (история чата).

        Поля, зависящие от запроса/пользователя, передаются явно: is_read (по
        watermark текущего пользователя), attachments/reactions (грузятся одним
        запросом на все сообщения — против N+1). Автор — из self.author
        (полиморфный).
        """
        data = {
            "id": self.id,
            "body": self.body,
            "message_type": self.message_type,
            "create_datetime": self.create_datetime.isoformat(),
            "starred": self.starred,
            "pinned": self.pinned,
            "is_edited": self.is_edited,
            "is_read": is_read,
            "parent_id": self.parent_id,
            "connector_id": self.connector_id,
            "connector_type": self.connector_type,
            "author": self.author,
            "attachments": attachments,
            "reactions": reactions,
            "is_deleted": self.is_deleted is True,
            "send_failed": self.send_failed is True,
        }

        return data

    def serialize_for_list(self) -> dict:
        """Короткая форма — результаты поиска и закреплённые сообщения."""
        return {
            "id": self.id,
            "body": self.body,
            "message_type": self.message_type,
            "connector_type": self.connector_type,
            "create_datetime": self.create_datetime.isoformat(),
            "author": self.author,
        }

    @hybridmethod
    async def post_message(
        self,
        chat_id: int,
        author_user_id: int | None = None,
        author_partner_id: int | None = None,
        body: str = "",
        message_type: str = "comment",
        connector_id: int | None = None,
        parent_id: int | None = None,
        lead_id: int | None = None,
        task_id: int | None = None,
    ):
        """
        Создать и отправить сообщение в чат.

        Args:
            chat_id: ID чата
            author_user_id: ID автора-пользователя (для операторов)
            author_partner_id: ID автора-партнёра (для внешних клиентов)
            body: Текст сообщения
            message_type: Тип сообщения
            connector_id: ID коннектора для внешней отправки
            parent_id: ID родительского сообщения (для ответов)

        Returns:
            Созданное сообщение
        """
        # Получаем объекты связанных записей
        chat = env.models.chat(id=chat_id)

        author = None
        if author_user_id:
            author = env.models.user(id=author_user_id)

        author_partner = None
        if author_partner_id:
            author_partner = env.models.partner(id=author_partner_id)

        connector = None
        # connector_type денормализуем в сообщение при создании — чтобы фронт
        # знал канал (email → HTML) без join и без пометки message_type.
        # Грузим тип отдельным лёгким SELECT: у connector здесь только id.
        connector_type = None
        if connector_id:
            connector = env.models.chat_connector(id=connector_id)
            _conn = await env.models.chat_connector.search_one(
                filter=[("id", "=", connector_id)],
                fields=["id", "type"],
            )
            connector_type = _conn.type if _conn else None

        parent = None
        if parent_id:
            parent = env.models.chat_message(id=parent_id)

        lead = None
        if lead_id:
            lead = env.models.lead(id=lead_id)

        task = None
        if task_id:
            task = env.models.task(id=task_id)

        now = datetime.now(timezone.utc)
        message = ChatMessage(
            body=body,
            message_type=message_type,
            chat_id=chat,
            author_user_id=author,
            author_partner_id=author_partner,
            connector_id=connector,
            connector_type=connector_type,
            parent_id=parent,
            lead_id=lead,
            task_id=task,
            create_datetime=now,
            update_datetime=now,
        )

        message.id = await self.create(payload=message)

        # Обновляем дату последнего сообщения в чате
        await chat.update_last_message_date()

        return message

    @hybridmethod
    async def send(
        self,
        chat_id: int,
        author: "User",
        body: str,
        files: list,
        connector_id: int | None = None,
        parent_id: int | None = None,
        lead_id: int | None = None,
        task_id: int | None = None,
    ) -> tuple["ChatMessage", list[dict]]:
        """Сообщение пользователя в чат: сохранить с вложениями, отправить во
        внешний канал, оповестить участников.

        files — загруженные файлы (name, mimetype, size, content, is_voice).
        Возвращает сообщение и его вложения в форме REST.

        Внешняя отправка идёт после коммита: запрос к провайдеру не держит
        транзакцию. Не ушло — сообщение остаётся и помечается send_failed.
        """
        async with env.apps.db.get_transaction() as session:
            message = await self.post_message(
                chat_id=chat_id,
                author_user_id=author.id,
                body=body,
                connector_id=connector_id,
                parent_id=parent_id,
                lead_id=lead_id,
                task_id=task_id,
            )
            attachments = [
                env.models.attachment(
                    name=file.name,
                    mimetype=file.mimetype,
                    size=file.size,
                    content=file.content,  # уже bytes
                    res_model="chat_message",
                    res_id=message.id,
                    is_voice=file.is_voice,
                )
                for file in files
            ]
            if attachments:
                # records — [{id: ...}, ...] в том же порядке, что attachments
                records = await env.models.attachment.create_bulk(
                    attachments, session=session
                )
                for attachment, record in zip(attachments, records or []):
                    attachment.id = record["id"]

        if connector_id and not await message._send_external(
            connector_id, author.id, attachments
        ):
            await message.update(ChatMessage(send_failed=True))

        # Та же форма, что в GET /messages и во входящем WS-пуше.
        attachments_data = [a.serialize_for_chat() for a in attachments]
        await env.apps.chat.chat_manager.send_to_chat(
            chat_id=chat_id,
            message={
                "type": "new_message",
                "chat_id": chat_id,
                "message": message.serialize_for_ws(
                    author={
                        "id": author.id,
                        "name": author.name,
                        "type": "user",
                    },
                    attachments=attachments_data,
                    # Теги «ленты»: фронт роутит событие в ленту лида/задачи.
                    # partner_id тут НЕ шлём (потребовал бы лишний запрос);
                    # во входящем пути он есть даром и идёт в пейлоаде.
                    lead_id=lead_id,
                    task_id=task_id,
                ),
            },
            exclude_user=author.id,
        )
        return message, attachments_data

    async def _send_external(
        self, connector_id: int, user_id: int, attachments: list
    ) -> bool:
        """Отправить сообщение через коннектор во внешний канал.
        False — не ушло."""
        # sudo: право отправлять — это право писать в чат (его проверил
        # вызывающий), коннектор здесь только канал. Токены коннектора
        # (role_read) сотруднику не видны.
        connector = await env.models.chat_connector.sudo().search_one(
            filter=[("id", "=", connector_id), ("active", "=", True)],
            fields_nested={
                "outbox_account_id": {"fields": ["id", "external_id"]}
            },
        )
        if not connector:
            return False

        recipients = await self.chat_id.get_recipients(connector, user_id)
        return bool(
            await connector.strategy.sudo().send_outgoing_message(
                env,
                chat_id=self.chat_id.id,
                connector_id=connector,
                user_id=user_id,
                body=self.body,
                message_id=self.id,
                attachments=attachments,
                recipients_ids=recipients,
            )
        )

    @hybridmethod
    async def post_system_message(
        self,
        chat_id: int,
        event: str,
        params: dict | None = None,
    ) -> None:
        """Создать системное сообщение чата и разослать подписчикам через WS.

        Системные сообщения — события уровня чата (участник добавлен/удалён,
        покинул чат и т.п.), которые на фронте рисуются пилюлей в стиле
        Telegram: без аватара, без пузыря, без автора.

        В `body` кладётся JSON `{"event": "...", "params": {...}}` —
        человекочитаемую строку формирует фронт через i18n (локализация без
        миграций, устойчивость к переименованию пользователей). На бэке
        сохраняется с message_type="system" и author_user_id=SYSTEM_USER_ID.

        Ошибки логируются и глотаются: сбой в косметике не должен ронять
        основную операцию чата (добавление/удаление участника и т.п.).
        """
        from backend.base.crm.users.models.users import SYSTEM_USER_ID

        try:
            body = json.dumps(
                {"event": event, "params": params or {}}, ensure_ascii=False
            )

            message = await env.models.chat_message.post_message(
                chat_id=chat_id,
                author_user_id=SYSTEM_USER_ID,
                body=body,
                message_type="system",
            )

            await env.apps.chat.chat_manager.send_to_chat(
                chat_id=chat_id,
                message={
                    "type": "new_message",
                    "chat_id": chat_id,
                    "message": message.serialize_for_ws(
                        author={
                            "id": SYSTEM_USER_ID,
                            "name": None,
                            "type": "user",
                        },
                        attachments=[],
                    ),
                },
            )
        except Exception as exc:
            _log.warning(
                "post_system_message failed: chat_id=%s event=%s "
                "params=%s err=%s",
                chat_id,
                event,
                params,
                exc,
            )

    @hybridmethod
    async def get_chat_messages(
        self,
        chat_id: int,
        limit: int = 50,
        before_id: int | None = None,
        include_deleted: bool = False,
    ):
        """
        Получить сообщения чата с пагинацией.

        Args:
            chat_id: ID чата
            limit: Максимальное количество сообщений
            before_id: Получить сообщения до указанного ID (для бесконечной прокрутки)

        Returns:
            Список сообщений
        """
        filter_conditions: "FilterExpression" = [
            ("chat_id", "=", chat_id),
        ]
        if not include_deleted:
            filter_conditions.append(("is_deleted", "=", False))

        if before_id:
            filter_conditions.append(("id", "<", before_id))

        messages = await self.search(
            filter=filter_conditions,
            fields=[
                "id",
                "body",
                "message_type",
                "author_user_id",
                "author_partner_id",
                "create_datetime",
                "starred",
                "pinned",
                "is_edited",
                "is_deleted",
                "send_failed",
                "parent_id",
                "connector_id",
                "connector_type",
                "lead_id",
                "task_id",
                "call_direction",
                "call_disposition",
                "call_duration",
                "call_talk_duration",
                "call_answer_time",
                "call_end_time",
            ],
            sort="id",
            order="DESC",
            limit=limit,
        )

        return messages

    @hybridmethod
    async def search_chat_messages(
        self, chat_id: int, query: str, limit: int = 50
    ):
        """
        Сообщения чата по подстроке текста (ILIKE), новые первыми.

        Для модалки поиска в открытом чате (лупа в шапке). Удалённые не
        ищем; поля — как у закреплённых: это список результатов, не лента.
        """
        return await self.search(
            filter=[
                ("chat_id", "=", chat_id),
                ("is_deleted", "=", False),
                ("body", "ilike", query),
            ],
            fields=[
                "id",
                "body",
                "message_type",
                "connector_type",
                "author_user_id",
                "author_partner_id",
                "create_datetime",
            ],
            sort="id",
            order="DESC",
            limit=limit,
        )

    @hybridmethod
    async def get_pinned_messages(self, chat_id: int):
        """
        Получить закрепленные сообщения чата.

        Args:
            chat_id: ID чата

        Returns:
            Список закрепленных сообщений
        """
        messages = await self.search(
            filter=[
                ("chat_id", "=", chat_id),
                ("is_deleted", "=", False),
                ("pinned", "=", True),
            ],
            fields=[
                "id",
                "body",
                "message_type",
                "connector_type",
                "author_user_id",
                "author_partner_id",
                "create_datetime",
            ],
            sort="create_datetime",
            order="DESC",
            limit=50,
        )

        return messages

    @classmethod
    async def last_by_chat(cls, chat_ids: list[int]) -> dict[int, dict]:
        """Последнее сообщение каждого чата — превью для списка чатов."""
        rows = await cls._get_db_session().execute(
            """
            SELECT DISTINCT ON (m.chat_id)
                m.id, m.chat_id, m.body, m.message_type, m.connector_type,
                m.create_datetime,
                COALESCE(m.author_user_id, m.author_partner_id) AS author_id,
                COALESCE(u.name, p.name) AS author_name
            FROM chat_message m
            LEFT JOIN users u ON u.id = m.author_user_id
            LEFT JOIN partners p ON p.id = m.author_partner_id
            WHERE m.chat_id = ANY(%s) AND m.is_deleted = false
            ORDER BY m.chat_id, m.id DESC
            """,
            (chat_ids,),
        )
        return {
            row["chat_id"]: {
                "id": row["id"],
                "body": row["body"],
                "message_type": row["message_type"],
                "connector_type": row["connector_type"],
                "author_id": row["author_id"],
                "author_name": row["author_name"],
                "create_datetime": (
                    row["create_datetime"].isoformat()
                    if row["create_datetime"]
                    else None
                ),
            }
            for row in rows
        }

    @classmethod
    async def unread_counts(
        cls, user_id: int, chat_ids: list[int] | None = None
    ) -> list[dict]:
        """Непрочитанные пользователя по чатам:
        [{chat_id, chat_type, is_internal, unread_count}], только где они есть.

        Непрочитанное — чужое неудалённое сообщение чата, где пользователь
        активный участник, с id больше его watermark
        (chat_member.last_read_message_id). chat_ids — считать в этих чатах;
        без него — во всех активных, кроме заметок записей (как в списке
        чатов).
        """
        scope = "c.active = true AND c.chat_type != 'record'"
        params: list = [user_id, user_id]
        if chat_ids is not None:
            scope = "m.chat_id = ANY(%s)"
            params.append(chat_ids)

        return await cls._get_db_session().execute(
            f"""
            SELECT m.chat_id, c.chat_type, c.is_internal,
                   COUNT(*) AS unread_count
            FROM chat_message m
            JOIN chat_member cm
              ON cm.chat_id = m.chat_id
             AND cm.user_id = %s
             AND cm.is_active = true
            JOIN chat c ON c.id = m.chat_id
            WHERE m.is_deleted = false
              AND (m.author_user_id IS NULL OR m.author_user_id != %s)
              AND m.id > COALESCE(cm.last_read_message_id, 0)
              AND {scope}
            GROUP BY m.chat_id, c.chat_type, c.is_internal
            """,
            tuple(params),
        )
