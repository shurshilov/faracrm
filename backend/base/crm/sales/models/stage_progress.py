"""
StageProgressMixin — прогресс записи (лида, заказа), который при попадании на
стадию берётся из стадии, а дальше правится руками в форме.

У стадии два поля: progress (прогресс по умолчанию) и progress_auto
(проставлять ли его). Запись получает progress стадии при создании и при
смене stage_id — если у стадии включено progress_auto и прогресс не передан
в том же запросе явно (ручное значение всегда важнее). В форме то же самое
делает /onchange по stage_id: слайдер сразу показывает значение стадии, и
его можно поправить до сохранения. Правка прогресса самой стадии старые
записи не трогает.

Использование (у модели должен быть Many2one `stage_id` на модель стадии):
    class Lead(AuditMixin, StageProgressMixin, PolymorphicParentMixin): ...
"""

from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod, onchange
from backend.base.system.dotorm.dotorm.fields import Integer

if TYPE_CHECKING:
    from backend.base.system.dotorm.dotorm.model import DotModel

    _Base = DotModel
else:
    _Base = object


class StageProgressMixin(_Base):
    # Прогресс (0–100): при попадании на стадию берётся из неё, дальше — руками.
    progress: int = Integer(string="Progress %", default=0)

    @classmethod
    async def _stage_progress(cls, stage_ref) -> int | None:
        """Прогресс по умолчанию стадии (запись или id). None — стадии нет
        или авто-проставление у неё выключено."""
        stage_id = getattr(stage_ref, "id", stage_ref)
        if not stage_id:
            return None
        stage_model = cls.get_fields()["stage_id"].relation_table
        if stage_model:
            stage = await stage_model.search_one(
                filter=[("id", "=", stage_id)],
                fields=["progress", "progress_auto"],
            )
            if not stage or not stage.progress_auto:
                return None
            return int(stage.progress or 0)
        return None

    @classmethod
    async def _apply_stage_progress(
        cls, payload, fields: list[str]
    ) -> list[str]:
        """create/update: стадия меняется, а прогресс явно не передан →
        прогресс стадии. Возвращает fields (+ progress, если проставили)."""
        if "stage_id" not in fields or "progress" in fields:
            return fields
        progress = await cls._stage_progress(payload.stage_id)
        if progress is None:
            return fields
        payload.progress = progress
        return [*fields, "progress"]

    @onchange("stage_id")
    async def onchange_stage_id(self) -> dict:
        """В форме сменили стадию → слайдер прогресса на её значение."""
        progress = await self._stage_progress(self.stage_id)
        return {} if progress is None else {"progress": progress}

    @hybridmethod
    async def create(self, payload, session=None, depends_jobs=None) -> int:
        await self._apply_stage_progress(payload, payload.assigned_fields())
        return await super().create(payload, session, depends_jobs)

    async def update(
        self, payload, fields=None, session=None, depends_jobs=None
    ):
        fields = await self._apply_stage_progress(
            payload, fields or payload.assigned_fields()
        )
        return await super().update(payload, fields, session, depends_jobs)
