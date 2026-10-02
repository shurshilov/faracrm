# Copyright 2025 FARA CRM
# Chat module - chat folder model (domain-based)
#
# Папка чатов = сохранённый domain-фильтр над моделью chat. Встроенные
# разделы (Сотрудники/Клиенты/Каналы/Документы) — не папки, а
# Chat.SECTION_SQL; здесь только папки пользователей:
#   - своя (user_id = владелец) — пользователь создаёт/видит/правит/удаляет
#     только свои. CRUD — auto-CRUD;
#   - общая (user_id IS NULL) — её заводит администратор, видят все.
#
# Набор чатов задаётся полем domain (JSON) — обычный FARA-домен над chat:
#   [["chat_type", "=", "direct"]]. Конкретные чаты — оператором `in`/`not in`
# по id (через domain-билдер на фронте), отдельных include/exclude полей нет.

import logging
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Many2one,
    JSONField,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.dotorm.dotorm.access import get_access_session
from backend.base.system.core.enviroment import env
from backend.base.crm.users.audit_mixin import AuditMixin

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.crm.users.models.users import User


def _default_current_user():
    """Текущий user_id из сессии (владелец при auto-CRUD create)."""
    session = get_access_session()
    return session.user_id if session else None


class ChatFolder(AuditMixin, DotModel):
    """Папка чатов: сохранённый domain-фильтр над chat."""

    __table__ = "chat_folder"

    id: int = Integer(primary_key=True)

    user_id: "User | None" = Many2one(
        relation_table=lambda: env.models.user,
        default=_default_current_user,
        description="Владелец папки. NULL - общая. Кастомная - текущий юзер.",
        index=True,
    )

    name: str = Char(max_length=255, description="Название папки")
    icon: str | None = Char(max_length=64, description="Токен иконки")
    color: str | None = Char(max_length=32, description="Цвет (опц.)")
    sequence: int = Integer(default=0, description="Порядок в сайдбаре")

    # Domain-фильтр над chat (формат как в rules.domain). [] / None → все чаты.
    domain: list | dict | None = JSONField(default=None)
