from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel


class TaskTag(DotModel):
    __table__ = "task_tag"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Tag Name", required=True)
    color: str = Char(string="Color", default="#868e96")
    active: bool = Boolean(default=True)


INITIAL_TASK_TAGS = [
    {"name": "Баг", "color": "#e03131"},
    {"name": "Фича", "color": "#1c7ed6"},
    {"name": "Улучшение", "color": "#37b24d"},
    {"name": "Срочно", "color": "#f59f00"},
    {"name": "Документация", "color": "#7048e8"},
]
