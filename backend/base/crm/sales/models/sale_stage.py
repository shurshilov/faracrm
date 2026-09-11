from backend.base.system.dotorm.dotorm.decorators import depends
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

    # Процент воронки (0–100): 100 у последней активной стадии, остальные
    # пропорционально sequence. Зависит от всей таблицы (максимум), а не
    # от полей одной строки — поэтому @depends() без триггеров: после
    # любой операции над стадиями пересчитываются все стадии.
    # Sale.progress копирует его через prefetch stage_id.progress.
    progress: int = Integer(
        string="Progress %", default=0, compute="_compute_progress"
    )

    @depends()
    async def _compute_progress(self) -> None:
        last = await self.search_one(
            filter=[("active", "=", True)],
            fields=["sequence"],
            sort="sequence",
            order="DESC",
        )
        top = int(last.sequence or 0) if last else 0
        sequence = int(self.sequence or 0)
        self.progress = (
            min(100, round(sequence * 100 / top))
            if top > 0 and sequence > 0
            else 0
        )


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
