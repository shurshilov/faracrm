# Copyright 2025 FARA CRM
# Chat module - message model

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
    PolymorphicOne2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.partners.models.partners import Partner
    from backend.base.crm.chat.models.chat import Chat
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.chat.models.chat_external_message import (
        ChatExternalMessage,
    )
    from backend.base.crm.attachments.models.attachments import Attachment


class ChatMessage(DotModel):
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
    res_model: str | None = Char(
        description="Модель записи к которой привязано сообщение (lead, task, partner...)",
    )

    res_id: int | None = Integer(
        description="ID записи к которой привязано сообщение",
    )

    # Временные метки
    create_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc), description="Дата создания"
    )
    write_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc),
        description="Дата изменения",
    )

    # Статус
    is_read: bool = Boolean(default=False, description="Прочитано")
    is_deleted: bool = Boolean(
        default=False, description="Удалено (мягкое удаление)"
    )

    # Связь с внешними системами (для интеграции)
    connector_id: "ChatConnector | None" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        description="Коннектор, через который отправлено/получено сообщение",
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
        relation_table=lambda: env.models.chat_message,
        description="Родительское сообщение (для ответов)",
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
        attachment_ids: list[int] | None = None,
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
        if connector_id:
            connector = env.models.chat_connector(id=connector_id)

        parent = None
        if parent_id:
            parent = env.models.chat_message(id=parent_id)

        now = datetime.now(timezone.utc)
        message = ChatMessage(
            body=body,
            message_type=message_type,
            chat_id=chat,
            author_user_id=author,
            author_partner_id=author_partner,
            connector_id=connector,
            parent_id=parent,
            create_date=now,
            write_date=now,
        )

        message.id = await self.create(payload=message)

        # Обновляем дату последнего сообщения в чате
        await chat.update_last_message_date()

        # Связываем вложения с сообщением
        if attachment_ids:
            for att_id in attachment_ids:
                attachment = env.models.attachment(id=att_id)
                await attachment.update(
                    env.models.attachment(
                        res_id=message.id, res_model="chat_message"
                    )
                )

        return message

    @hybridmethod
    async def get_chat_messages(
        self,
        chat_id: int,
        limit: int = 50,
        before_id: int | None = None,
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
        filter_conditions = [
            ("chat_id", "=", chat_id),
            ("is_deleted", "=", False),
        ]

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
                "create_date",
                "starred",
                "pinned",
                "is_edited",
                "is_read",
                "parent_id",
                "connector_id",
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
                "create_date",
                "pinned",
            ],
            sort="create_date",
            order="DESC",
            limit=50,
        )

        return messages

    async def mark_as_read(self, message_ids: list[int]) -> int:
        """Отметить сообщения как прочитанные."""
        return await self.update_bulk(
            ids=message_ids,
            payload=ChatMessage(is_read=True),
        )

    @hybridmethod
    async def mark_chat_as_read(self, chat_id: int, user_id: int) -> int:
        """Отметить все сообщения в чате как прочитанные для пользователя."""
        # Находим все непрочитанные сообщения в чате от других авторов
        # (включая сообщения от партнёров)
        unread = await self.search(
            filter=[
                ("chat_id", "=", chat_id),
                ("is_read", "=", False),
                # ("author_user_id", "!=", user_id),
                [
                    ("author_user_id", "!=", user_id),
                    "or",
                    ("author_user_id", "=", None),
                ],
            ],
            fields=["id"],
        )

        if unread:
            ids = [m.id for m in unread]
            return await self.mark_as_read(ids)

        return 0

    async def soft_delete(self) -> bool:
        """Мягкое удаление сообщения."""
        await self.update(
            ChatMessage(
                is_deleted=True,
                write_date=datetime.now(timezone.utc),
            )
        )
        return True

    @hybridmethod
    async def mark_as_unread(
        self, chat_id: int, message_id: int, user_id: int
    ) -> int:
        """
        Отметить сообщения как непрочитанные начиная с указанного.

        Помечает все сообщения в чате с ID >= message_id как непрочитанные,
        кроме сообщений текущего пользователя.

        Args:
            chat_id: ID чата
            message_id: ID сообщения, начиная с которого помечать
            user_id: ID текущего пользователя (его сообщения не помечаем)

        Returns:
            Количество помеченных сообщений
        """
        messages = await self.search(
            filter=[
                ("chat_id", "=", chat_id),
                ("id", ">=", message_id),
                [
                    ("author_user_id", "!=", user_id),
                    "or",
                    ("author_user_id", "=", None),
                ],
                ("is_deleted", "=", False),
            ],
            fields=["id"],
        )

        if messages:
            ids = [m.id for m in messages]
            await self.update_bulk(
                ids=ids,
                payload=ChatMessage(is_read=False),
            )
            return len(ids)

        return 0
