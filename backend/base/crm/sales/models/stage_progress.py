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

Одна реализация на список записей (_apply_stage_progress): create и update
передают [payload], create_bulk — всю пачку; стадии грузятся одним SELECT.

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


def _stage_id(stage_ref) -> int | None:
    """id стадии из записи или числа (у payload бывает и то, и то)."""
    return getattr(stage_ref, "id", stage_ref) or None


class StageProgressMixin(_Base):
    # Прогресс (0–100): при попадании на стадию берётся из неё, дальше — руками.
    progress: int = Integer(string="Progress %", default=0)

    @classmethod
    async def _stage_progress_by_id(
        cls, stage_ids: set[int]
    ) -> dict[int, int]:
        """Прогресс по умолчанию стадий одним SELECT: {id: progress} только
        для стадий с включённым progress_auto."""
        if not stage_ids:
            return {}
        stage_model = cls.get_fields()["stage_id"].relation_table
        stages = await stage_model.search(
            filter=[("id", "in", list(stage_ids))],
            fields=["id", "progress", "progress_auto"],
        )
        return {s.id: int(s.progress or 0) for s in stages if s.progress_auto}

    @classmethod
    async def _apply_stage_progress(cls, payloads: list, fields) -> list[str]:
        """create/create_bulk/update: у записей, где стадия меняется, а
        прогресс явно не передан, — прогресс стадии. fields — поля операции
        (у bulk объединённые); возвращает их же (+ progress, если проставили
        хоть одной записи)."""
        if "stage_id" not in fields:
            return fields
        todo = [
            p
            for p in payloads
            if "progress" not in p.assigned_fields() and _stage_id(p.stage_id)
        ]
        by_id = await cls._stage_progress_by_id(
            {_stage_id(p.stage_id) for p in todo}
        )
        applied = False
        for p in todo:
            progress = by_id.get(_stage_id(p.stage_id))
            if progress is not None:
                p.progress = progress
                applied = True
        if applied and "progress" not in fields:
            return [*fields, "progress"]
        return fields

    @onchange("stage_id")
    async def onchange_stage_id(self) -> dict:
        """В форме сменили стадию → слайдер прогресса на её значение."""
        stage_id = _stage_id(self.stage_id)
        by_id = (
            await self._stage_progress_by_id({stage_id}) if stage_id else {}
        )
        return {"progress": by_id[stage_id]} if stage_id in by_id else {}

    @hybridmethod
    async def create(self, payload, session=None, depends_jobs=None) -> int:
        await self._apply_stage_progress([payload], payload.assigned_fields())
        return await super().create(payload, session, depends_jobs)

    @hybridmethod
    async def create_bulk(self, payload, session=None, depends_jobs=None):
        fields: set[str] = set()
        for p in payload:
            fields.update(p.assigned_fields())
        await self._apply_stage_progress(payload, fields)
        return await super().create_bulk(payload, session, depends_jobs)

    async def update(
        self, payload, fields=None, session=None, depends_jobs=None
    ):
        fields = await self._apply_stage_progress(
            [payload], fields or payload.assigned_fields()
        )
        return await super().update(payload, fields, session, depends_jobs)
