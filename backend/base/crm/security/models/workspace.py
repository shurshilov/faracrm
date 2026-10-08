# Copyright 2025 FARA CRM
# Security module — «Рабочее место» (цифровое рабочее место)

from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Integer,
    Many2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.system.apps.models.apps import App


class Workspace(DotModel):
    """
    «Рабочее место» (цифровое рабочее место) — именованный набор
    UI-приложений, который админ назначает пользователям.

    ВАЖНО: это ПРЕЗЕНТАЦИОННЫЙ слой (курирование меню), НЕ безопасность.
    Скрытие приложения из лаунчера НЕ ограничивает доступ к данным — их
    по-прежнему защищают ACL и Rules на сервере. «Рабочее место» лишь
    определяет, какие приложения показывать пользователю в интерфейсе
    (разгрузить меню под должность: «РМ Менеджер», «РМ Склад» и т.п.).

    app_ids — приложения (App с ui_menu=true), видимые в этом РМ. Фронту
    отдаётся их ui_menu_name (= ключи групп меню: communication, crm, …);
    App.code остаётся кодом МОДУЛЯ (chat, leads, …). Пустой набор →
    приложения не показываются. Видимость меню теперь определяется ТОЛЬКО
    «Рабочим местом»: у пользователя без РМ (User.workspace_id = NULL)
    приложений не видно (кроме суперпользователя is_admin). Роли остаются для
    доступа к данным (ACL/Rules), но меню больше не курируют.
    """

    __table__ = "workspace"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=128, required=True)
    active: bool = Boolean(default=True)
    sequence: int = Integer(default=10, description="Порядок")

    # Приложения РМ. m2m к App (осмысленно — только ui_menu=true; пикер на
    # фронте фильтрует по ui_menu). Каталог приложений живёт в БД, поэтому
    # список берётся запросом, а не статикой. column1/column2 — по образцу
    # User.role_ids: column1 = «другая» сторона (app_id), column2 = «своя»
    # (workspace_id), это компенсирует порядок вставки в link_many2many.
    app_ids: list["App"] = Many2many(
        store=False,
        relation_table=lambda: env.models.app,
        many2many_table="workspace_app_many2many",
        column1="app_id",
        column2="workspace_id",
        ondelete="cascade",
        default=[],
    )
