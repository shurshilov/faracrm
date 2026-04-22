# Copyright 2025 FARA CRM
# Tasks module - project member (via MemberMixin).

from typing import TYPE_CHECKING

from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Integer,
    Many2one,
)
from backend.base.system.membership import MemberMixin

if TYPE_CHECKING:
    from backend.base.crm.tasks.models.project import Project


class ProjectMember(MemberMixin):
    """
    Участник проекта.
    Общие поля/методы — из MemberMixin.
    """

    __table__ = "project_member"
    # __auto_crud__ = False

    _member_res_field = "project_id"
    _member_res_model = staticmethod(lambda: env.models.project)

    id: int = Integer(primary_key=True)

    project_id: "Project" = Many2one(
        relation_table=lambda: env.models.project,
        description="Проект",
        index=True,
    )

    # Права для проектных ролей
    can_read: bool = Boolean(default=True, description="Может видеть проект")
    can_write: bool = Boolean(
        default=True, description="Может писать в задачи"
    )
    can_assign: bool = Boolean(
        default=False, description="Может назначать исполнителей"
    )
    can_invite: bool = Boolean(
        default=False, description="Может приглашать участников"
    )
    can_archive: bool = Boolean(
        default=False, description="Может архивировать проект"
    )
