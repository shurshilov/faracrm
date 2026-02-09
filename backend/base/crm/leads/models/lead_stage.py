from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel


class LeadStage(DotModel):
    __table__ = "lead_stage"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Stage Name", required=True)
    sequence: int = Integer(string="Sequence", default=10)
    active: bool = Boolean(default=True)
    fold: bool = Boolean(default=False, string="Folded in Kanban")
    color: str = Char(string="Color", default="#3498db")


INITIAL_LEAD_STAGES = [
    {
        "name": "Новый",
        "sequence": 10,
        "active": True,
        "fold": False,
        "color": "#17a2b8",
    },
    {
        "name": "Квалификация",
        "sequence": 20,
        "active": True,
        "fold": False,
        "color": "#ffc107",
    },
    {
        "name": "Предложение",
        "sequence": 30,
        "active": True,
        "fold": False,
        "color": "#fd7e14",
    },
    {
        "name": "Переговоры",
        "sequence": 40,
        "active": True,
        "fold": False,
        "color": "#6f42c1",
    },
    {
        "name": "Выиграно",
        "sequence": 50,
        "active": True,
        "fold": False,
        "color": "#28a745",
    },
    {
        "name": "Проиграно",
        "sequence": 60,
        "active": True,
        "fold": True,
        "color": "#dc3545",
    },
]
