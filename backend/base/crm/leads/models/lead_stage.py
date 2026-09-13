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

    # Прогресс по умолчанию (0–100): лид получает его при попадании на
    # стадию (StageProgressMixin), дальше правится в лиде руками.
    progress: int = Integer(string="Default progress %", default=0)
    # Выключено → лидам на этой стадии прогресс не проставляется, только руками.
    # default_db: колонка добавляется в старые базы с DEFAULT TRUE, чтобы у
    # уже существующих стадий проставление было включено без миграций.
    progress_auto: bool = Boolean(
        default=True, default_db=True, string="Auto-set progress"
    )


INITIAL_LEAD_STAGES = [
    {
        "name": "Новый",
        "sequence": 10,
        "active": True,
        "fold": False,
        "color": "#17a2b8",
        "progress": 10,
    },
    {
        "name": "Квалификация",
        "sequence": 20,
        "active": True,
        "fold": False,
        "color": "#ffc107",
        "progress": 30,
    },
    {
        "name": "Предложение",
        "sequence": 30,
        "active": True,
        "fold": False,
        "color": "#fd7e14",
        "progress": 50,
    },
    {
        "name": "Переговоры",
        "sequence": 40,
        "active": True,
        "fold": False,
        "color": "#6f42c1",
        "progress": 75,
    },
    {
        "name": "Выиграно",
        "sequence": 50,
        "active": True,
        "fold": False,
        "color": "#28a745",
        "progress": 100,
    },
    {
        "name": "Проиграно",
        "sequence": 60,
        "active": True,
        "fold": True,
        "color": "#dc3545",
        "progress": 0,
    },
]
