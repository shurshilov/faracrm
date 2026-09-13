from typing import Type

# from backend.base.crm.users.audit_mixin import AuditMixin
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.dotorm.dotorm.fields import PolymorphicOne2many


class ModelsCore:
    """Структура для работы с моделями."""

    _table_to_model_name: dict[str, str] = {}
    _table_to_model_class: dict[str, Type[DotModel]] = {}
    # Полиморфные дети: (имя модели в env, поле-связь у родителей,
    # дефолтный фильтр). Собирается из __polymorphic_field__ дочерних
    # моделей (activity, attachment, chat); PolymorphicParentMixin по нему
    # каскадит удаление.
    _polymorphic_children: list[tuple[str, str, list | None]] = []

    def _build_table_mapping(self):
        """Строит маппинг table_name → model_name + таблицы @depends.
        Возвращает self для chaining."""
        for model_name in dir(self):
            if model_name.startswith("_"):
                continue
            model_cls = getattr(self, model_name)
            # Проверяем что это класс (не метод) с __table__
            if isinstance(model_cls, type) and hasattr(model_cls, "__table__"):
                self._table_to_model_name[model_cls.__table__] = model_name
                self._table_to_model_class[model_cls.__table__] = model_cls

                # Встраиваем AuditMixin in-place — все импорты
                # `from .models import Partner` остаются валидными.
                # if AuditMixin not in model_cls.__mro__:
                #     model_cls.__bases__ = (AuditMixin,) + model_cls.__bases__
                #     model_cls._build_field_cache()

        self._attach_polymorphic_fields()
        # TODO: refactor
        # @depends: собираем таблицы триггеров _depends_local_triggers и
        # _depends_parent_triggers по всем зарегистрированным моделям.
        # Cross-model инверсию (parent_triggers на детях) нельзя собрать
        # на уровне __init_subclass__ одной модели — нужно знать все
        # модели сразу, поэтому делаем это здесь, после регистрации.
        #
        # ВАЖНО: _build_depends_tables разворачивает dotted-deps вида
        # "order_line_ids.X" и для этого читает field.relation_table.
        # У One2many/Many2one relation_table обычно объявлен лямбдой
        # `lambda: env.models.X` — лямбда дёргается прямо здесь. Чтобы
        # она резолвилась, привязываем self к env.models ДО билда
        # таблиц. Внешнее `env.models = Models()._build_table_mapping()`
        # потом запишет тот же объект ещё раз — идемпотентно.
        from backend.base.system.core.enviroment import env as _env

        _env.models = self

        from backend.base.system.dotorm.dotorm.orm.mixins.primary import (
            OrmPrimaryMixin,
        )

        OrmPrimaryMixin._build_depends_tables(
            self._table_to_model_class.values()
        )

        return self

    def _attach_polymorphic_fields(self):
        """Поля-связи на полиморфных детей — КАЖДОЙ модели, автоматически.

        Дочерняя модель объявляет
            __polymorphic_field__ = ("activity_ids", [("active", "=", True)])
        — имя поля у родителей и дефолтный фильтр среза. Дети ключуются по
        res_model (= __table__ родителя) / res_id, поэтому родителем может
        быть любая таблица: лид, заказ, стадия лида, тег. Модель со своим
        одноимённым полем (ChatMessage.attachment_ids) оставляет своё; сами
        дети друг на друга поля не получают.
        """
        type(self)._polymorphic_children = [
            (
                self._table_to_model_name[table],
                *model_cls.__polymorphic_field__,
            )
            for table, model_cls in self._table_to_model_class.items()
            if getattr(model_cls, "__polymorphic_field__", None)
        ]
        children = {
            getattr(self, model_name)
            for model_name, _, _ in self._polymorphic_children
        }
        for model_cls in self._table_to_model_class.values():
            if model_cls in children:
                continue
            for (
                model_name,
                field_name,
                default_filter,
            ) in self._polymorphic_children:
                if field_name not in model_cls.get_fields():
                    model_cls.add_field(
                        field_name,
                        self._polymorphic_field(model_name, default_filter),
                    )

    def _polymorphic_field(self, model_name: str, default_filter: list | None):
        """Поле-связь на полиморфного ребёнка model_name."""
        return PolymorphicOne2many(
            relation_table=lambda: getattr(self, model_name),
            relation_table_field="res_id",
            filter=list(default_filter) if default_filter else None,
        )

    def _get_model_name_by_table(self, model: str):
        return self._table_to_model_name[model]

    def _get_model_class_by_table(self, model: str):
        return self._table_to_model_class[model]

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
