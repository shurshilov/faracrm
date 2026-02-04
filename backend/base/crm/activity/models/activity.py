from datetime import datetime, date, timezone
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Text,
    Boolean,
    Date,
    Datetime,
    Selection,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.activity.models.activity_type import ActivityType


class Activity(DotModel):
    """
    Запланированная активность привязанная к записи.

    Полиморфная привязка через res_model + res_id (как Attachment).
    При наступлении дедлайна создаёт notification в системном чате.
    """

    __table__ = "activity"

    id: int = Integer(primary_key=True)

    # Полиморфная привязка к записи
    res_model: str = Char(
        max_length=255,
        required=True,
        description="Модель записи (lead, task, partner...)",
    )
    res_id: int = Integer(
        required=True,
        description="ID записи",
    )

    # Тип активности
    activity_type_id: "ActivityType" = Many2one(
        relation_table=lambda: env.models.activity_type,
        required=True,
        description="Тип активности",
    )

    # Содержание
    summary: str | None = Char(max_length=255, description="Краткое описание")
    note: str | None = Text(description="Подробное описание")

    # Дедлайн
    date_deadline: date = Date(
        required=True,
        description="Дата завершения",
    )

    # Назначение
    user_id: "User" = Many2one(
        relation_table=lambda: env.models.user,
        required=True,
        description="Кому назначено",
    )
    create_user_id: "User | None" = Many2one(
        relation_table=lambda: env.models.user,
        description="Кто создал",
    )

    # Состояние
    state: str = Selection(
        options=[
            ("planned", "Planned"),
            ("today", "Today"),
            ("overdue", "Overdue"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="planned",
        description="Состояние: planned/today/overdue/done/cancelled",
    )

    done: bool = Boolean(default=False, description="Выполнена")
    done_datetime: datetime | None = Datetime(description="Когда выполнена")

    active: bool = Boolean(default=True)

    # Даты
    create_date: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc),
        description="Дата создания",
    )

    # Флаг: было ли уже отправлено уведомление
    notification_sent: bool = Boolean(
        default=False,
        description="Уведомление отправлено",
    )

    @hybridmethod
    async def mark_done(self, activity_id: int, user_id: int):
        """
        Пометить активность как выполненную.
        Создаёт notification-сообщение в системном чате.
        """
        activities = await self.search(
            filter=[("id", "=", activity_id)],
            fields=[
                "id",
                "summary",
                "res_model",
                "res_id",
                "user_id",
                "activity_type_id",
            ],
            limit=1,
        )
        if not activities:
            return None

        activity = activities[0]
        now = datetime.now(timezone.utc)

        # Обновляем активность
        await activity.update(
            Activity(done=True, done_datetime=now, state="done")
        )

        # Создаём notification в системном чате
        summary = activity.summary or "Активность"
        type_name = ""
        if activity.activity_type_id:
            type_name = f"[{activity.activity_type_id.name}] "

        await self._send_notification(
            user_id=activity.user_id.id,
            body=f"✅ {type_name}{summary} — выполнена",
            res_model=activity.res_model,
            res_id=activity.res_id,
        )

        return activity

    @hybridmethod
    async def schedule_activity(
        self,
        res_model: str,
        res_id: int,
        activity_type_id: int,
        user_id: int,
        summary: str | None = None,
        note: str | None = None,
        date_deadline: date | None = None,
        create_user_id: int | None = None,
    ):
        """
        Запланировать новую активность.
        """
        # Если дедлайн не указан — берём default_days из типа
        if date_deadline is None:
            types = await env.models.activity_type.search(
                filter=[("id", "=", activity_type_id)],
                fields=["id", "default_days"],
                limit=1,
            )
            default_days = types[0].default_days if types else 1
            from datetime import timedelta

            date_deadline = date.today() + timedelta(days=default_days)

        activity = Activity(
            res_model=res_model,
            res_id=res_id,
            activity_type_id=env.models.activity_type(id=activity_type_id),
            user_id=env.models.user(id=user_id),
            create_user_id=(
                env.models.user(id=create_user_id) if create_user_id else None
            ),
            summary=summary,
            note=note,
            date_deadline=date_deadline,
            state="today" if date_deadline == date.today() else "planned",
        )

        activity.id = await self.create(payload=activity)
        return activity

    @hybridmethod
    async def _send_notification(
        self,
        user_id: int,
        body: str,
        res_model: str | None = None,
        res_id: int | None = None,
    ):
        """
        Отправить notification через системный чат.
        Создаёт ChatMessage type=notification в системном чате пользователя.
        Отправляет через WebSocket для реалтайма.
        """
        # Находим или создаём системный чат для пользователя
        system_chat_id = await self._get_or_create_system_chat(user_id)

        # Создаём сообщение
        message = await env.models.chat_message.post_message(
            chat_id=system_chat_id,
            body=body,
            message_type="notification",
        )

        # Привязываем к записи (через extend поля)
        if res_model and res_id:
            await message.update(
                env.models.chat_message(
                    res_model=res_model, res_id=res_id
                )
            )

        # Отправляем через WebSocket
        try:
            from backend.base.crm.chat import chat_manager

            await chat_manager.send_to_user(
                user_id,
                {
                    "type": "notification",
                    "message": {
                        "id": message.id,
                        "body": body,
                        "res_model": res_model,
                        "res_id": res_id,
                        "create_date": (
                            message.create_date.isoformat()
                            if message.create_date
                            else None
                        ),
                    },
                },
            )
        except Exception:
            pass  # WS не обязателен

        return message

    @hybridmethod
    async def _get_or_create_system_chat(self, user_id: int) -> int:
        """
        Получить или создать системный чат для пользователя.
        Системный чат — direct чат с name='FARA System' для конкретного user.
        """
        from backend.base.crm.chat.models.chat import Chat

        # Ищем существующий системный чат по имени и участнику
        chats = await env.models.chat.search(
            filter=[
                ("name", "=", f"__system__{user_id}"),
                ("chat_type", "=", "direct"),
            ],
            fields=["id"],
            limit=1,
        )

        if chats:
            return chats[0].id

        # Создаём новый системный чат
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        chat = Chat(
            name=f"__system__{user_id}",
            chat_type="direct",
            active=True,
            is_internal=True,
            create_date=now,
            write_date=now,
        )
        chat.id = await env.models.chat.create(payload=chat)

        # Добавляем пользователя как участника
        from backend.base.crm.chat.models.chat_member import ChatMember

        member = ChatMember(
            chat_id=env.models.chat(id=chat.id),
            user_id=env.models.user(id=user_id),
        )
        await env.models.chat_member.create(payload=member)

        return chat.id

    @hybridmethod
    async def check_deadlines(self):
        """
        Крон-задача: проверяет дедлайны и отправляет уведомления.
        Вызывается периодически (например каждый час).
        """
        today = date.today()

        # 1. Обновляем state для просроченных
        overdue = await self.search(
            filter=[
                ("date_deadline", "<", str(today)),
                ("done", "=", False),
                ("state", "!=", "overdue"),
                ("state", "!=", "cancelled"),
            ],
            fields=["id", "state"],
        )
        for activity in overdue:
            await activity.update(Activity(state="overdue"))

        # 2. Обновляем state для сегодняшних
        today_activities = await self.search(
            filter=[
                ("date_deadline", "=", str(today)),
                ("done", "=", False),
                ("state", "=", "planned"),
            ],
            fields=["id", "state"],
        )
        for activity in today_activities:
            await activity.update(Activity(state="today"))

        # 3. Отправляем уведомления для сегодняшних и просроченных (если ещё не отправляли)
        pending = await self.search(
            filter=[
                ("date_deadline", "<=", str(today)),
                ("done", "=", False),
                ("notification_sent", "=", False),
                ("state", "!=", "cancelled"),
            ],
            fields=[
                "id",
                "summary",
                "res_model",
                "res_id",
                "user_id",
                "activity_type_id",
                "date_deadline",
                "state",
            ],
        )

        for activity in pending:
            type_name = ""
            if activity.activity_type_id:
                type_name = f"[{activity.activity_type_id.name}] "

            summary = activity.summary or "Активность"
            is_overdue = activity.state == "overdue"
            emoji = "🔴" if is_overdue else "🔔"
            status = "просрочена" if is_overdue else "на сегодня"

            await self._send_notification(
                user_id=activity.user_id.id,
                body=f"{emoji} {type_name}{summary} — {status}",
                res_model=activity.res_model,
                res_id=activity.res_id,
            )

            await activity.update(Activity(notification_sent=True))
