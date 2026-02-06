from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from .project import Project
    from .task_stage import TaskStage
    from .task_tag import TaskTag

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


class Task(DotModel):
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
    name: str = Char(string="Task Title", required=True, size=500)
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
    date_start: datetime = Datetime(string="Start Date")
    date_end: datetime = Datetime(string="End Date")
    date_deadline: datetime | None = Datetime(string="Deadline")

    #  Трекинг времени
    planned_hours: float | None = Float(string="Planned Hours", default=0)
    effective_hours: float | None = Float(string="Spent Hours", default=0)

    #  Прогресс (0-100)
    progress: int | None = Integer(string="Progress %", default=0)

    #  Цвет (для канбана/ганта)
    color: str = Char(string="Color", default="#1c7ed6")
