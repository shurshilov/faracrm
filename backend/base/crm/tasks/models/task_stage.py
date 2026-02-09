from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel


class TaskStage(DotModel):
    __table__ = "task_stage"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Stage Name", required=True)
    sequence: int = Integer(string="Sequence", default=10)
    active: bool = Boolean(default=True)
    fold: bool = Boolean(default=False, string="Folded in Kanban")
    color: str = Char(string="Color", default="#3498db")
    is_closed: bool = Boolean(
        default=False,
        string="Closing Stage",
    )


INITIAL_TASK_STAGES = [
    {"name": "Новая", "sequence": 10, "color": "#868e96", "is_closed": False},
    {
        "name": "В работе",
        "sequence": 20,
        "color": "#1c7ed6",
        "is_closed": False,
    },
    {
        "name": "На проверке",
        "sequence": 30,
        "color": "#f59f00",
        "is_closed": False,
    },
    {
        "name": "Готово",
        "sequence": 40,
        "color": "#37b24d",
        "is_closed": True,
        "fold": True,
    },
    {
        "name": "Отменена",
        "sequence": 50,
        "color": "#e03131",
        "is_closed": True,
        "fold": True,
    },
]
