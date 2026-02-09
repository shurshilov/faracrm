from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.model import DotModel


class SaleStage(DotModel):
    __table__ = "sale_stage"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Stage Name", required=True)
    sequence: int = Integer(string="Sequence", default=10)
    active: bool = Boolean(default=True)
    fold: bool = Boolean(default=False, string="Folded in Kanban")
    color: str = Char(string="Color", default="#3498db")


INITIAL_SALE_STAGES = [
    {
        "name": "Черновик",
        "sequence": 10,
        "active": True,
        "fold": False,
        "color": "#6c757d",
    },
    {
        "name": "Отправлено",
        "sequence": 20,
        "active": True,
        "fold": False,
        "color": "#17a2b8",
    },
    {
        "name": "Подтверждено",
        "sequence": 30,
        "active": True,
        "fold": False,
        "color": "#28a745",
    },
    {
        "name": "Выполнено",
        "sequence": 40,
        "active": True,
        "fold": False,
        "color": "#007bff",
    },
    {
        "name": "Отменено",
        "sequence": 50,
        "active": True,
        "fold": True,
        "color": "#dc3545",
    },
]
