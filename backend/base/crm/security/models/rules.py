from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Integer,
    JSONField,
    Many2one,
    JSONField,
)
from backend.base.system.dotorm.dotorm.model import DotModel

from .models import Model
from .roles import Role


class Rule(DotModel):
    """
    Правила доступа к записям (Row-level security).

    Правила определяют, какие записи пользователь может видеть/изменять.
    Фильтрация происходит через domain — JSON-выражение в формате:
        [("field", "op", value), ...]

    Поддерживаемые переменные в domain:
        - {{user_id}} или {{user.id}} — ID текущего пользователя

    Пример domain:
        [("user_id", "=", "{{user_id}}")]  — только свои записи
        [("team_id", "in", [1, 2, 3])]     — записи определённых команд
        [("active", "=", true), ("owner_id", "=", "{{user_id}}")]  — AND условия

    Если у пользователя несколько правил на одну модель/операцию,
    они объединяются через OR (достаточно попасть под любое правило).
    """

    __table__ = "rules"

    id: int = Integer(primary_key=True)
    name: str = Char(required=True, max_length=256)
    active: bool = Boolean(default=True)

    # Модель, к которой применяется правило
    model_id: Model | None = Many2one(relation_table=Model)

    # Роль, для которой действует правило (NULL = для всех)
    role_id: Role | None = Many2one(relation_table=Role)

    # Domain-фильтр в формате JSON
    # Пример: '[("user_id", "=", "{{user_id}}")]'
    domain: list | dict | None = JSONField(default=None)

    # Права на операции
    perm_create: bool = Boolean(default=False)
    perm_read: bool = Boolean(default=True)
    perm_update: bool = Boolean(default=False)
    perm_delete: bool = Boolean(default=False)
