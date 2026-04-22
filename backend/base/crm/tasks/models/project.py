from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User
    from .task import Task

from .project_member import ProjectMember
from backend.base.system.dotorm.dotorm.access import get_access_session
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Text,
    Many2one,
    One2many,
    Selection,
    Datetime,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env


def _default_current_user():
    session = get_access_session()
    return session.user_id if session else None


class Project(DotModel):
    """
    Проект — группировка задач.

    Простая сущность: название, описание, ответственный, статус.
    Задачи ссылаются на проект через project_id.
    """

    __table__ = "project"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Project Name", required=True)
    active: bool = Boolean(default=True)
    description: str | None = Text(string="Description")
    color: str = Char(string="Color", default="#1c7ed6")

    status: str = Selection(
        options=[
            ("active", "Active"),
            ("on_hold", "On Hold"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="active",
        string="Status",
    )

    manager_id: "User" = Many2one(
        lambda: env.models.user,
        string="Project Manager",
        ondelete="restrict",
        default=_default_current_user,
    )

    date_start: datetime | None = Datetime(string="Start Date")
    date_end: datetime | None = Datetime(string="End Date")

    member_ids: list["ProjectMember"] = One2many(
        store=False,
        relation_table=lambda: env.models.project_member,
        relation_table_field="project_id",
        description="Участники проекта",
    )

    task_ids: list["Task"] = One2many(
        lambda: env.models.task,
        store=False,
        relation_table_field="project_id",
        string="Tasks",
    )
