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

    # Автор сообщения (пользователь системы - оператор)
    author_user_id: "User | None" = Many2one(
        relation_table=lambda: env.models.user,
        description="Автор - пользователь системы (для операторов)",
    )

    # Автор сообщения (партнёр - внешний клиент)
    author_partner_id: "Partner | None" = Many2one(
        relation_table=lambda: env.models.partner,
        description="Автор - партнёр (для внешних клиентов)",
    )

    # иногда сообщение может быть привязано к записи модели
    # res_model: str | None = Char(
    #     description="Модель записи к которой привязано сообщение (lead, task, partner...)",
    # )

    # res_id: int | None = Integer(
    #     description="ID записи к которой привязано сообщение",
    # )

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

    @property
    def author(self) -> dict | None:
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
        return None

    def serialize_for_ws(
        self,
        *,
        author: dict,
        attachments: list[dict],
        connector_type: str | None = None,
        author_user_id: int | None = None,
        author_partner_id: int | None = None,
        partner_id: int | None = None,
        lead_id: int | None = None,
        body_limit: int | None = None,
    ) -> dict:
        """Форма сообщения для WS-события `new_message` (входящий путь).

        Часть данных не выводится из самого сообщения и передаётся явно:
        author (у входящего имя — контрагента, а не автора-стаба),
        attachments (уже сериализованы, см. Attachment.serialize_for_chat),
        partner_id/lead_id — теги «ленты». body_limit обрезает тело (входящий
        шлёт превью в 200 символов; пустое тело → None, 1:1 с прежним
        `body[:200] if body else None`).
        """
        body = self.body
        if body_limit is not None:
            body = body[:body_limit] if body else None
        return {
            "id": self.id,
            "body": body,
            "author": author,
            "author_user_id": author_user_id,
            "author_partner_id": author_partner_id,
            "partner_id": partner_id,
            "lead_id": lead_id,
            "create_datetime": (
                self.create_datetime.isoformat()
                if self.create_datetime
                else None
            ),
            "connector_type": connector_type,
            "attachments": attachments,
        }

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
        (полиморфный), с тем же фолбэком Unknown, что был в
        format_message_author.
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
            "author": self.author
            or {"id": None, "name": "Unknown", "type": None},
            "attachments": attachments,
            "reactions": reactions,
            "is_deleted": self.is_deleted is True,
        }

        return data

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
        # attachment_ids: list[int] | None = None,
        # res_model: str | None = None,
        # res_id: int | None = None,
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
            attachment_ids: Список ID вложений

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
            _conn = await env.models.chat_connector.search(
                filter=[("id", "=", connector_id)],
                fields=["id", "type"],
                limit=1,
            )
            connector_type = _conn[0].type if _conn else None

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
            # res_model=res_model,
            # res_id=res_id,
        )

        message.id = await self.create(payload=message)

        # Обновляем дату последнего сообщения в чате
        await chat.update_last_message_date()

        # Связываем вложения с сообщением
        # if attachment_ids:
        #     for att_id in attachment_ids:
        #         attachment = env.models.attachment(id=att_id)
        #         await attachment.update(
        #             env.models.attachment(
        #                 res_id=message.id, res_model="chat_message"
        #             )
        #         )

        return message

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
                    "message": {
                        "id": message.id,
                        "body": body,
                        "message_type": "system",
                        "author": {
                            "id": SYSTEM_USER_ID,
                            "name": None,
                            "type": "user",
                        },
                        "create_datetime": message.create_datetime.isoformat(),
                        "starred": False,
                        "pinned": False,
                        "is_edited": False,
                        "is_read": False,
                        "attachments": [],
                    },
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
                "author_user_id",
                "author_partner_id",
                "create_datetime",
                # "pinned",
            ],
            sort="create_datetime",
            order="DESC",
            limit=50,
        )

        return messages

    # async def soft_delete(self) -> bool:
    #     """Мягкое удаление сообщения."""

    #     await self.update(
    #         ChatMessage(
    #             is_deleted=True,
    #             update_datetime=datetime.now(timezone.utc),
    #         )
    #     )
    #     return True
