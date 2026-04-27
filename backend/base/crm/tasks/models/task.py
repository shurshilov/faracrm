from typing import TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from .project import Project
    from .task_stage import TaskStage
    from .task_tag import TaskTag

from backend.base.system.dotorm.dotorm.access import get_access_session
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Text,
    Many2one,
    Many2many,
    One2many,
    Selection,
    Datetime,
    Float,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.users.audit_mixin import AuditMixin


def _default_current_user():
    session = get_access_session()
    return session.user_id if session else None


async def _default_stage_id():
    """Метод для получения стадии по умолчанию"""
    first_stage = await env.models.task_stage.search(
        fields=["id", "name"],
        limit=1,
    )
    return first_stage[0] if first_stage else None


async def _default_name():
    """Генерирует имя заказа вида 'Заказ 0000042' на основе следующего id
    из sequence таблицы sales."""
    session = env.apps.db.get_session()
    # Postgres: nextval гарантирует уникальное значение,
    # которое будет использовано при следующем INSERT
    result = await session.execute(
        "SELECT nextval(pg_get_serial_sequence('tasks', 'id')) AS next_id"
    )
    next_id = result[0]["next_id"] if result else 0
    return f"Задача {str(next_id).zfill(7)}"


class Task(AuditMixin, DotModel):
    """
    Задача (task) — основная сущность модуля.

    Агрегирует лучшие практики:
      - parent_id → self-referencing для подзадач
      - project_id → группировка в проекты
      - stage_id → канбан-статусы
      - user_id → ответственный
      - date_start / date_end → для Ганта
      - priority / tag_ids → классификация
      - planned_hours / effective_hours → трекинг времени
    """

    __table__ = "tasks"

    id: Id = Integer(primary_key=True)
    name: str = Char(
        string="Task Title", required=True, size=500, default=_default_name
    )
    active: bool = Boolean(default=True)
    sequence: int = Integer(default=10, string="Sequence")

    #  Описание
    description: str | None = Text(string="Description")

    #  Связь с проектом
    project_id: "Project" = Many2one(
        lambda: env.models.project,
        string="Project",
        index=True,
        ondelete="restrict",
    )

    #  Стадия (канбан)
    stage_id: "TaskStage" = Many2one(
        lambda: env.models.task_stage,
        string="Stage",
        index=True,
        ondelete="restrict",
        default=_default_stage_id,
    )

    #  Подзадачи: self-referencing
    parent_id: "Task | None" = Many2one(
        lambda: env.models.task,
        string="Parent Task",
        index=True,
        ondelete="cascade",
    )
    child_ids: list["Task"] = One2many(
        lambda: env.models.task,
        store=False,
        relation_table_field="parent_id",
        string="Subtasks",
    )

    #  Назначение
    user_id: "User" = Many2one(
        lambda: env.models.user,
        string="Assignee",
        index=True,
        ondelete="restrict",
        default=_default_current_user,
    )

    #  Приоритет
    priority: str = Selection(
        options=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        default="medium",
        string="Priority",
    )

    #  Теги
    tag_ids: list["TaskTag"] = Many2many(
        lambda: env.models.task_tag,
        store=False,
        string="Tags",
        many2many_table="task_tag_many2many",
        column1="tag_id",
        column2="task_id",
        description="Теги этого таска",
        default=[],
    )

    #  Даты (для Ганта)
    date_start: datetime = Datetime(
        string="Start Date",
        default=lambda: datetime.now(timezone.utc),
    )
    date_end: datetime | None = Datetime(string="End Date")
    date_deadline: datetime | None = Datetime(string="Deadline")

    #  Трекинг времени
    planned_hours: float | None = Float(string="Planned Hours", default=0)
    effective_hours: float | None = Float(string="Spent Hours", default=0)

    #  Прогресс (0-100)
    progress: int | None = Integer(string="Progress %", default=0)

    #  Цвет (для канбана/ганта)
    color: str = Char(string="Color", default="#1c7ed6")
