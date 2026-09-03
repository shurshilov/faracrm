# Copyright 2025 FARA CRM
# Chat module - chat folder model (domain-based)
#
# Папка чатов = сохранённый domain-фильтр над моделью chat.
#
# Три вида папок:
#   1. Встроенные глобальные (user_id IS NULL, kind = all|direct|group) —
#      «Все»/«Личные»/«Группы». Видны всем, не редактируются пользователем.
#   2. Папка коннектора (user_id IS NULL, connector_id = <id>) — одна на
#      коннектор, глобальная. Её чаты резолвятся по connector_id (не domain).
#   3. Пользовательские (user_id = владелец, kind = NULL, connector_id = NULL) —
#      пользователь создаёт/видит/правит/удаляет только свои. CRUD — auto-CRUD.
#
# Набор чатов задаётся полем domain (JSON) — обычный FARA-домен над chat:
#   [["chat_type", "=", "direct"]]. Конкретные чаты — оператором `in`/`not in`
# по id (через domain-билдер на фронте), отдельных include/exclude полей нет.

import logging
from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
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
    from backend.project_setup import ChatConnector


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
        description="Владелец папки. NULL - глобальная. Кастомная - текущий юзер.",
        index=True,
    )

    name: str = Char(max_length=255, description="Название папки")
    icon: str | None = Char(max_length=64, description="Токен иконки")
    color: str | None = Char(max_length=32, description="Цвет (опц.)")
    sequence: int = Integer(default=0, description="Порядок в сайдбаре")

    # Domain-фильтр над chat (формат как в rules.domain). [] / None → все чаты.
    domain: list | dict | None = JSONField(default=None)

    # Вид встроенной глобальной папки: all | direct | group. NULL у остальных.
    kind: str | None = Char(
        max_length=32, description="Вид встроенной папки (all/direct/group)"
    )

    # Папка коннектора (глобальная): FK на коннектор. NULL у остальных.
    # Чаты такой папки резолвятся по connector_id через chat_external_chat.
    connector_id: "ChatConnector | None" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        ondelete="cascade",
        description="Коннектор (для глобальной папки коннектора)",
        index=True,
    )

    @hybridmethod
    async def ensure_global_defaults(self) -> None:
        """Создать глобальные «Все»/«Личные»/«Группы», если их ещё нет."""

        for folder in DEFAULT_GLOBAL_FOLDERS:
            existing = await self.search(
                filter=[
                    ("user_id", "=", None),
                    ("kind", "=", folder.kind),
                ],
                fields=["id"],
                limit=1,
            )
            if existing:
                continue
            await self.create(payload=folder)

    @hybridmethod
    async def ensure_connector_folder(
        self,
        connector_id: int,
        connector_name: str,
        sequence: int = 100,
    ) -> None:
        """Глобальная папка коннектора (idempotent по connector_id)."""

        existing = await self.search(
            filter=[
                ("user_id", "=", None),
                ("connector_id", "=", connector_id),
            ],
            fields=["id"],
            limit=1,
        )

        if existing:
            return

        await self.create(
            payload=env.models.chat_folder(
                user_id=None,
                connector_id=env.models.chat_connector(id=connector_id),
                name=connector_name,
                icon="connector",
                sequence=sequence,
                domain=None,
            )
        )


# Встроенные глобальные папки. user_id=None задан ЯВНО: иначе create()
# подставит default поля — текущего пользователя сессии (в post_init это
# системный), папка перестанет быть глобальной, и проверка «уже есть?» выше
# (user_id IS NULL) будет сеять её заново при каждом старте.
# Домены — обычные над chat.
# ВНУТРЕННИЕ папки фильтруют is_internal=true: без этого условия внешние
# (клиентские) чаты — chat_type='group', is_internal=false — попадали и во
# внутренние «Все»/«Группы» (они уже показаны в секции «Внешние»).
DEFAULT_GLOBAL_FOLDERS = [
    ChatFolder(
        user_id=None,
        kind="all",
        name="Все",
        icon="all",
        domain=[["is_internal", "=", True]],
        sequence=0,
    ),
    ChatFolder(
        user_id=None,
        kind="direct",
        name="Личные",
        icon="direct",
        domain=[["chat_type", "=", "direct"], ["is_internal", "=", True]],
        sequence=10,
    ),
    ChatFolder(
        user_id=None,
        kind="group",
        name="Группы",
        icon="group",
        domain=[
            ["chat_type", "in", ["group", "channel"]],
            ["is_internal", "=", True],
        ],
        sequence=20,
    ),
    # Внешние (клиентские) чаты. Резолвятся get_chats по kind, НЕ доменом:
    # членство ("Мои") и team-видимость ("Все") не выразить доменом над chat.
    #   - external_all:  is_internal=false + (участник ИЛИ chat.team_id ∈ мои
    #                    команды) — team-scoped обзор;
    #   - external_mine: is_internal=false + только где я участник.
    ChatFolder(
        user_id=None,
        kind="external_all",
        name="Все",
        icon="external_all",
        domain=None,
        sequence=30,
    ),
    ChatFolder(
        user_id=None,
        kind="external_mine",
        name="Мои",
        icon="external_mine",
        domain=None,
        sequence=40,
    ),
]
