from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Text,
    Boolean,
    Datetime,
    Selection,
    Many2one,
    Field,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.core.enviroment import env
from backend.base.crm.chat.models.chat import Chat
from backend.base.crm.chat.models.chat_member import ChatMember
from backend.base.system.dotorm.dotorm.access import get_access_session

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from backend.base.crm.activity.models.activity_type import ActivityType


def _default_current_user():
    session = get_access_session()
    return session.user_id if session else None


class Activity(DotModel):
    """
    Запланированная активность привязанная к записи.

    Полиморфная привязка через res_model + res_id (как Attachment).
    При наступлении дедлайна создаёт notification в системном чате.
    """

    __table__ = "activity"

    id: int = Integer(primary_key=True)

    # Полиморфная привязка к записи
    res_model: str | None = Char(
        max_length=255,
        required=True,
        description="Модель записи (lead, task, partner...)",
    )
    res_id: int | None = Integer(
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
    date_deadline: datetime = Datetime(
        required=True,
        index=True,
        description="Дата завершения",
    )

    # Назначение
    user_id: "User" = Many2one(
        relation_table=lambda: env.models.user,
        required=True,
        index=True,
        description="Кому назначено",
        default=_default_current_user,
        # default=lambda: (
        #     s.user_id.json() if (s := get_access_session()) else None
        # ),
    )
    create_user_id: "User | None" = Many2one(
        relation_table=lambda: env.models.user,
        default=_default_current_user,
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
        index=True,
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

    # @hybridmethod
    # async def mark_done(self, activity_id: int, user_id: int):
    #     """
    #     Пометить активность как выполненную.
    #     Создаёт notification-сообщение в системном чате.
    #     """
    #     activities = await self.search(
    #         filter=[("id", "=", activity_id)],
    #         fields=[
    #             "id",
    #             "summary",
    #             "res_model",
    #             "res_id",
    #             "user_id",
    #             "activity_type_id",
    #         ],
    #         limit=1,
    #     )
    #     if not activities:
    #         return None

    #     activity = activities[0]
    #     now = datetime.now(timezone.utc)

    #     # Обновляем активность
    #     await activity.update(
    #         Activity(done=True, done_datetime=now, state="done")
    #     )

    #     # Создаём notification в системном чате
    #     summary = activity.summary or "Активность"
    #     type_name = ""
    #     if activity.activity_type_id:
    #         type_name = f"[{activity.activity_type_id.name}] "

    #     await self._send_notification(
    #         user_id=activity.user_id.id,
    #         body=f"✅ {type_name}{summary} — выполнена",
    #         res_model=activity.res_model,
    #         res_id=activity.res_id,
    #     )

    #     return activity

    async def update(
        self,
        payload: "Activity",
        fields: list[str] | None = None,
        session=None,
    ):
        """
        При переходе в state="done" автоматически:
        - active → False  (активность уходит из активных списков)
        - done → True
        - done_datetime → now (UTC)

        Делается ДО super().update(), чтобы все поля улетели одним
        SQL UPDATE — без второго round-trip к БД и без промежуточного
        состояния "done + active=true".
        """
        new_state = payload.state or None
        # Игнорируем дескриптор Field (поле не задано в payload)
        if not isinstance(new_state, Field) and new_state == "done":
            payload.active = False
            payload.done = True
            payload.done_datetime = datetime.now(timezone.utc)

            # Если вызывающий код передал явный список fields — добавляем
            # туда новые поля, чтобы они попали в SQL UPDATE.
            if fields is not None:
                extras = {"active", "done", "done_datetime"}
                fields = list({*fields, *extras})

        await super().update(payload, fields=fields, session=session)

    @hybridmethod
    async def update_bulk(
        self,
        ids: list[int],
        payload: "Activity",
        session=None,
    ):
        """
        То же поведение, что и в `update`: если массово переводим записи
        в state="done", то заодно деактивируем их и проставляем done /
        done_datetime — одним SQL UPDATE на все ids.

        Семантика идентична: payload — общий для всех ids, поэтому если
        в нём `state="done"` — всем переведённым записям проставится
        полный набор полей done.
        """
        new_state = getattr(payload, "state", None)
        if not isinstance(new_state, Field) and new_state == "done":
            payload.active = False
            payload.done = True
            payload.done_datetime = datetime.now(timezone.utc)

        return await super().update_bulk(ids, payload, session=session)

    @hybridmethod
    async def schedule_activity(
        self,
        res_model: str,
        res_id: int,
        activity_type_id: int,
        user_id: int,
        summary: str | None = None,
        note: str | None = None,
        date_deadline: datetime | None = None,
        create_user_id: int | None = None,
    ):
        """
        Запланировать новую активность.
        """
        now_utc = datetime.now(timezone.utc)

        if date_deadline is None:
            # Ищем тип активности, чтобы узнать дефолтный срок
            activity_types = await env.models.activity_type.search(
                filter=[("id", "=", activity_type_id)],
                fields=["default_days"],
                limit=1,
            )
            # Безопасно берем default_days или 1
            days = activity_types[0].default_days if activity_types else 1
            date_deadline = now_utc + timedelta(days=days)

        # Определяем статус (сравниваем даты в одном часовом поясе)
        state = (
            "today" if date_deadline.date() == now_utc.date() else "planned"
        )

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
            state=state,
        )

        activity.id = await self.create(activity)
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
            res_model=res_model,
            res_id=res_id,
        )

        # Отправляем через WebSocket
        try:
            await env.apps.chat.chat_manager.send_to_user(
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
            ...  # WS не обязателен

        return message

    @hybridmethod
    async def _get_or_create_system_chat(self, user_id: int) -> int:
        """
        Получить или создать системный чат для пользователя.
        Системный чат — direct чат с name='FARA System' для конкретного user.
        """

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
        member = ChatMember(
            chat_id=env.models.chat(id=chat.id),
            user_id=env.models.user(id=user_id),
        )
        await env.models.chat_member.create(payload=member)

        # Уведомляем пользователя о новом чате через WS
        try:
            await env.apps.chat.chat_manager.notify_new_chat(user_id, chat.id)
        except Exception:
            pass

        return chat.id

    @hybridmethod
    async def check_deadlines(self):
        """
        Крон-задача: проверяет дедлайны и отправляет уведомления.
        Вызывается периодически (например каждую минуту).
        """
        now = datetime.now(timezone.utc)

        # 1. Обновляем state для просроченных (дедлайн прошёл)
        overdue = await self.search(
            filter=[
                ("date_deadline", "<", now),
                ("done", "=", False),
                ("state", "!=", "overdue"),
                ("state", "!=", "cancelled"),
            ],
            fields=["id"],
        )
        await env.models.activity.update_bulk(
            [activity.id for activity in overdue], Activity(state="overdue")
        )

        # 2. Отправляем уведомления (дедлайн наступил и ещё не отправляли)
        pending = await self.search(
            filter=[
                ("date_deadline", "<=", now),
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
            status = "просрочена" if is_overdue else "срок наступил"

            await self._send_notification(
                user_id=activity.user_id.id,
                body=f"{emoji} {type_name}{summary} — {status}",
                res_model=activity.res_model,
                res_id=activity.res_id,
            )

            await activity.update(Activity(notification_sent=True))
