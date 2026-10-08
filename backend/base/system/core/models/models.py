"""
Реестр моделей — строка на каждую модель из project_setup (Models).

На него ссылается всё, что «про модель»: права и правила security,
маршруты вложений, сохранённые фильтры, настройки видов. Заполняет его
само ядро — Environment.start_post_init зовёт Model.seed до post_init
модулей, поэтому строки есть раньше, чем модули создают по ним права.
Права на реестр объявляет security, как и на остальные модели ядра
(system_settings).
"""

from typing import TYPE_CHECKING

from backend.base.system.dotorm.dotorm.fields import Char, Integer
from backend.base.system.dotorm.dotorm.model import DotModel

if TYPE_CHECKING:
    from backend.base.system.core.models import ModelsCore


class Model(DotModel):
    """Модель системы (строка на каждую модель из Models)."""

    __table__ = "models"

    id: int = Integer(primary_key=True)
    name: str = Char()
    table_name: str = Char()

    @classmethod
    async def seed(cls, models: "ModelsCore") -> None:
        """Создаёт записи для всех моделей (идемпотентно).

        Помимо name сохраняем table (__table__ модели) — так по связи
        model_id сразу доступно имя таблицы (напр. в маршрутах вложений),
        без обратного маппинга env-имя -> таблица. Для уже существующих
        записей table бэкфиллится идемпотентно.
        """
        models_names = models._get_models_names()
        if not models_names:
            return

        exist_models = await cls.search(
            filter=[("name", "in", models_names)],
            fields=["id", "name", "table_name"],
        )
        exist_by_name = {m.name: m for m in exist_models}

        for model_name in models_names:
            table = models._get_model(model_name).__table__
            existing = exist_by_name.get(model_name)
            if existing is None:
                await cls.create(
                    payload=cls(name=model_name, table_name=table)
                )
            elif table and existing.table_name != table:
                # Бэкфилл имени таблицы у ранее созданных записей реестра
                await existing.update(cls(table_name=table))
