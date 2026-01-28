from typing import Type

from backend.base.system.dotorm.dotorm.model import DotModel


class ModelsCore:
    """Структура для работы с моделями."""

    _table_to_model: dict[str, str] = {}

    def _build_table_mapping(self):
        """Строит маппинг table_name → model_name. Возвращает self для chaining."""
        for model_name in dir(self):
            if model_name.startswith("_"):
                continue
            model_cls = getattr(self, model_name)
            # Проверяем что это класс (не метод) с __table__
            if isinstance(model_cls, type) and hasattr(model_cls, "__table__"):
                self._table_to_model[model_cls.__table__] = model_name
        return self

    def _get_model_name_by_table(self, model):
        return self._table_to_model[model]

    def _get_models(self) -> list[Type[DotModel]]:
        return [
            getattr(self, model_name)
            for model_name in dir(self)
            if not model_name.startswith("_")
        ]

    def _get_models_names(self) -> list[str]:
        return [
            model_name
            for model_name in dir(self)
            if not model_name.startswith("_")
        ]

    def _get_model(self, model_class_name) -> Type[DotModel]:
        return getattr(self, model_class_name)
