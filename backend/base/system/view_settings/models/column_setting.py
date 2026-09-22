"""
Модель для хранения пользовательских настроек колонок списков.

Одна запись = набор видимых колонок конкретного пользователя для
конкретной модели (например: user_id=5, model_name="partners").
Хранится порядок и состав колонок таблицы (какие показывать/скрыть).
"""

import datetime
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Text,
    Many2one,
    Datetime,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.crm.users.models.users import User
from backend.base.system.dotorm.dotorm.access import get_access_session


def _default_current_user():
    """Текущий user_id из сессии (или None, если сессии нет)."""
    session = get_access_session()
    return session.user_id if session else None


class ColumnSetting(DotModel):
    """Настройки колонок списка (per-user, per-model)."""

    __table__ = "column_settings"

    id: int = Integer(primary_key=True)

    # Модель-справочник, к которой относится настройка
    # (например: 'partners', 'contact', 'leads').
    model_name: str = Char(required=True)

    # Пользователь-владелец настройки. По умолчанию — текущий из сессии.
    # Правила доступа (view_settings/app.py) ограничивают выборку своими
    # строками, поэтому у каждого пользователя свой набор колонок.
    user_id: "User | None" = Many2one(
        relation_table=User,
        default=_default_current_user,
        index=True,
    )

    # JSON-массив имён полей в порядке отображения:
    # ["id", "name", "company_id", ...]. Пустой массив [] = скрыть все
    # (кроме виртуальных колонок вью).
    columns: str = Text(required=True)

    # Настройки колонок-связей (One2many/Many2many/полиморфные) по имени
    # поля. widgets: {"activity_ids": "count"} — как рисовать (count —
    # плашка-счётчик, present — «есть/нет», text — текст). filters:
    # {"activity_ids": [["state", "=", "overdue"], ...]} — фильтр на
    # связанные записи в формате фильтра списков; уходит в search как
    # {имя: {"filter": [...]}} и складывается с Field.filter поля по И.
    widgets: str | None = Text()
    filters: str | None = Text()

    # Дата создания
    created_at: datetime.datetime = Datetime(
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        schema_required=False,
    )
