"""
Модель для хранения сохранённых фильтров пользователей.
"""

import datetime
from typing import TYPE_CHECKING
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Text,
    Many2one,
    Boolean,
    Datetime,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.crm.users.models.users import User


class SavedFilter(DotModel):
    """Сохранённый фильтр поиска."""

    __table__ = "saved_filters"

    id: int = Integer(primary_key=True)

    # Название фильтра
    name: str = Char(required=True)

    # Модель к которой применяется фильтр (например: 'users', 'partners')
    model_name: str = Char(required=True)

    # JSON с фильтрами: [["field", "op", "value"], "and", ...]
    filter_data: str = Text(required=True)

    # Пользователь-владелец фильтра
    user_id: "User | None" = Many2one(relation_table=User)

    # Глобальный фильтр (доступен всем)
    is_global: bool = Boolean(default=False)

    # Фильтр по умолчанию для модели
    is_default: bool = Boolean(default=False)

    # Дата создания
    created_at: datetime.datetime = Datetime(
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        schema_required=False,
    )

    # Дата последнего использования
    last_used_at: datetime.datetime | None = Datetime()

    # Счётчик использований
    use_count: int = Integer(default=0, schema_required=False)
