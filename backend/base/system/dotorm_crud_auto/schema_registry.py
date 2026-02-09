"""
Оптимизированный генератор Pydantic схем для CRUD операций.

Основные улучшения:
1. Кэширование - каждая схема создаётся только один раз
2. Батчевая генерация - все схемы для всех моделей за один проход
3. Простые функции вместо множества миксинов с __pydantic_init_subclass__
4. Нет рекурсивного создания вложенных схем в runtime

Использование:
    registry = SchemaRegistry()
    registry.build_all(models)  # Один раз при старте

    create_schema = registry.get_create_schema(User)
    update_schema = registry.get_update_schema(User)
"""

from typing import (
    Any,
    Literal,
    Optional,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
)
from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic.fields import FieldInfo

from backend.base.system.dotorm.dotorm.fields import (
    PolymorphicMany2one,
    PolymorphicOne2many,
    Many2many,
    Many2one,
    One2many,
)
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm_crud_auto.crud_pydantic_schemas import (
    SchemaRelationNested,
    SchemaSearchOutput,
    SchemaRelationMany2ManyUpdateCreate,
    SchemaRelationOne2ManyUpdateCreate,
)


# Типы отношений
RELATION_TYPES = (
    Many2one,
    Many2many,
    One2many,
    PolymorphicOne2many,
    PolymorphicMany2one,
)
MANY_RELATIONS = (Many2many, One2many, PolymorphicOne2many)
SINGLE_RELATIONS = (Many2one, PolymorphicMany2one)


class SchemaRegistry:
    """
    Реестр Pydantic схем с кэшированием.

    Генерирует и кэширует схемы для CRUD операций:
    - base: Базовая схема (все поля как есть)
    - create: Для создания (без id, связи как id/VirtualId)
    - update: Для обновления (partial + без id)
    - search_output: Для вывода списка (связи как {id, name})
    - read_output: Для вывода формы (вложенные связи как {id, name})
    """

    def __init__(self):
        self._base_schemas: dict[str, type[BaseModel]] = {}
        self._create_schemas: dict[str, type[BaseModel]] = {}
        self._update_schemas: dict[str, type[BaseModel]] = {}
        self._search_output_schemas: dict[str, type[BaseModel]] = {}
        self._read_output_schemas: dict[str, type[BaseModel]] = {}
        self._search_input_schemas: dict[str, type[BaseModel]] = {}
        self._triplets: dict[str, list] = {}
        self._built = False

    def build_all(self, models: list[type]) -> None:
        """
        Построить все схемы для всех моделей за один проход.

        Args:
            models: Список DotModel классов
        """
        if self._built:
            return

        import logging

        log = logging.getLogger(__name__)

        # Шаг 1: Создаём базовые схемы для всех моделей
        # (нужно сначала создать все, чтобы разрешить forward refs)
        from backend.base.system.dotorm.dotorm.integrations.pydantic import (
            generate_pydantic_models,
        )

        base_schemas = generate_pydantic_models(models)

        for model in models:
            name = model.__name__
            base = base_schemas[name]
            self._base_schemas[name] = base

            # Присваиваем __schema__ модели
            model.__schema__ = base

        # Шаг 2: Генерируем производные схемы
        errors = []
        for model in models:
            name = model.__name__
            base = self._base_schemas[name]

            try:
                # Create schema
                self._create_schemas[name] = self._build_create_schema(
                    name, base
                )

                # Update schema
                self._update_schemas[name] = self._build_update_schema(
                    name, base
                )

                # Search output schema
                self._search_output_schemas[name] = (
                    self._build_search_output_schema(name, base)
                )

                # Read output schema (с вложенными связями)
                self._read_output_schemas[name] = (
                    self._build_read_output_schema(name, base)
                )

                # Search input schema
                self._search_input_schemas[name] = (
                    self._build_search_input_schema(name, base, model)
                )

                # Triplets для фильтрации
                self._triplets[name] = self._build_search_triplets(base)

            except Exception as e:
                errors.append(f"{name}: {e}")
                log.error(f"Failed to build schemas for {name}: {e}")

        if errors:
            log.warning(
                f"Schema generation completed with {len(errors)} errors"
            )

        self._built = True

    def get_base_schema(self, model: type) -> type[BaseModel]:
        """Получить базовую схему."""
        name = model.__name__
        if name not in self._base_schemas:
            raise KeyError(
                f"Schema for '{name}' not found. Call build_all() first."
            )
        return self._base_schemas[name]

    def get_create_schema(self, model: type) -> type[BaseModel]:
        """Получить схему для создания."""
        name = model.__name__
        if name not in self._create_schemas:
            raise KeyError(
                f"Create schema for '{name}' not found. Call build_all() first."
            )
        return self._create_schemas[name]

    def get_update_schema(self, model: type) -> type[BaseModel]:
        """Получить схему для обновления."""
        name = model.__name__
        if name not in self._update_schemas:
            raise KeyError(
                f"Update schema for '{name}' not found. Call build_all() first."
            )
        return self._update_schemas[name]

    def get_search_output_schema(self, model: type) -> type[BaseModel]:
        """Получить схему для вывода списка."""
        name = model.__name__
        if name not in self._search_output_schemas:
            raise KeyError(
                f"Search output schema for '{name}' not found. Call build_all() first."
            )
        return self._search_output_schemas[name]

    def get_read_output_schema(self, model: type) -> type[BaseModel]:
        """Получить схему для вывода формы."""
        name = model.__name__
        if name not in self._read_output_schemas:
            raise KeyError(
                f"Read output schema for '{name}' not found. Call build_all() first."
            )
        return self._read_output_schemas[name]

    def get_search_input_schema(self, model: type) -> type[BaseModel]:
        """Получить схему для ввода поиска."""
        name = model.__name__
        if name not in self._search_input_schemas:
            raise KeyError(
                f"Search input schema for '{name}' not found. Call build_all() first."
            )
        return self._search_input_schemas[name]

    def get_triplets(self, model: type) -> list:
        """Получить триплеты для фильтрации."""
        name = model.__name__
        return self._triplets.get(name, [])

    def reset(self) -> None:
        """
        Сбросить все кэшированные схемы.
        Полезно для тестов или hot reload.
        """
        self._base_schemas.clear()
        self._create_schemas.clear()
        self._update_schemas.clear()
        self._search_output_schemas.clear()
        self._read_output_schemas.clear()
        self._search_input_schemas.clear()
        self._triplets.clear()
        self._built = False

    @property
    def is_built(self) -> bool:
        """Проверить построены ли схемы."""
        return self._built

    # ==================== Построение схем ====================

    def _build_create_schema(
        self, name: str, base: type[BaseModel]
    ) -> type[BaseModel]:
        """
        Схема для создания:
        - Без поля id
        - Many2one -> Id | VirtualId
        - Many2many/One2many -> список операций (add/remove/set)
        """
        fields = {}

        for field_name, field_info in base.model_fields.items():
            if field_name == "id":
                continue  # Пропускаем id

            metadata = self._get_field_metadata(field_info)

            if metadata and metadata[0] in RELATION_TYPES:
                # Трансформируем поле связи
                new_annotation = self._transform_relation_for_create(
                    field_info, metadata[0]
                )
                fields[field_name] = (
                    new_annotation,
                    self._get_default(field_info),
                )
            else:
                # Обычное поле - копируем как есть
                fields[field_name] = (
                    field_info.annotation,
                    self._get_default(field_info),
                )

        return create_model(
            f"{name}Create",
            __config__=ConfigDict(protected_namespaces=()),
            **fields,
        )

    def _build_update_schema(
        self, name: str, base: type[BaseModel]
    ) -> type[BaseModel]:
        """
        Схема для обновления:
        - Без поля id
        - Все поля опциональные (partial)
        - Связи как в create
        """
        fields = {}

        for field_name, field_info in base.model_fields.items():
            if field_name == "id":
                continue

            metadata = self._get_field_metadata(field_info)

            if metadata and metadata[0] in RELATION_TYPES:
                new_annotation = self._transform_relation_for_create(
                    field_info, metadata[0]
                )
                # Делаем опциональным
                fields[field_name] = (Optional[new_annotation], None)
            else:
                # Обычное поле - делаем опциональным
                fields[field_name] = (Optional[field_info.annotation], None)

        return create_model(
            f"{name}Update",
            __config__=ConfigDict(protected_namespaces=()),
            **fields,
        )

    def _build_search_output_schema(
        self, name: str, base: type[BaseModel]
    ) -> type[BaseModel]:
        """
        Схема для вывода списка (search):
        - Все поля опциональные
        - Связи как {id, name}
        """
        fields = {}

        for field_name, field_info in base.model_fields.items():
            metadata = self._get_field_metadata(field_info)

            if metadata and metadata[0] in RELATION_TYPES:
                if metadata[0] in SINGLE_RELATIONS:
                    fields[field_name] = (Optional[SchemaRelationNested], None)
                else:
                    fields[field_name] = (
                        Optional[list[SchemaRelationNested]],
                        None,
                    )
            else:
                fields[field_name] = (Optional[field_info.annotation], None)

        return create_model(
            f"{name}SearchOutput",
            __config__=ConfigDict(protected_namespaces=()),
            **fields,
        )

    def _build_read_output_schema(
        self, name: str, base: type[BaseModel]
    ) -> type[BaseModel]:
        """
        Схема для вывода формы (read):
        - Все поля опциональные
        - Вложенные связи (2 уровень) как {id, name}
        """
        fields = {}

        for field_name, field_info in base.model_fields.items():
            metadata = self._get_field_metadata(field_info)

            if metadata and metadata[0] in RELATION_TYPES:
                # Получаем Pydantic схему связанной модели
                related_schema = self._get_schema_origin(field_info)

                if (
                    related_schema
                    and isinstance(related_schema, type)
                    and issubclass(related_schema, BaseModel)
                ):
                    # Создаём вложенную схему где связи уже как {id, name}
                    nested = self._build_nested_schema_from_pydantic(
                        related_schema
                    )

                    if metadata[0] in SINGLE_RELATIONS:
                        fields[field_name] = (Optional[nested], None)
                    else:
                        fields[field_name] = (
                            Optional[SchemaSearchOutput[list[nested]]],
                            None,
                        )
                else:
                    # Fallback - просто {id, name}
                    if metadata[0] in SINGLE_RELATIONS:
                        fields[field_name] = (
                            Optional[SchemaRelationNested],
                            None,
                        )
                    else:
                        fields[field_name] = (
                            Optional[list[SchemaRelationNested]],
                            None,
                        )
            else:
                fields[field_name] = (Optional[field_info.annotation], None)

        return create_model(
            f"{name}ReadOutput",
            __config__=ConfigDict(protected_namespaces=()),
            **fields,
        )

    def _build_nested_schema_from_pydantic(
        self, pydantic_schema: type[BaseModel]
    ) -> type[BaseModel]:
        """
        Схема для вложенных связей (2 уровень) из Pydantic схемы.
        Связи внутри как {id, name}.
        """
        cache_key = f"{pydantic_schema.__name__}Nested"

        # Проверяем кэш
        if cache_key in self._search_output_schemas:
            return self._search_output_schemas[cache_key]

        fields = {}

        for field_name, field_info in pydantic_schema.model_fields.items():
            metadata = self._get_field_metadata(field_info)

            if metadata and metadata[0] in RELATION_TYPES:
                # На 2 уровне все связи как {id, name}
                if metadata[0] in SINGLE_RELATIONS:
                    fields[field_name] = (Optional[SchemaRelationNested], None)
                else:
                    fields[field_name] = (
                        Optional[list[SchemaRelationNested]],
                        None,
                    )
            else:
                fields[field_name] = (Optional[field_info.annotation], None)

        schema = create_model(
            cache_key, __config__=ConfigDict(protected_namespaces=()), **fields
        )

        # Кэшируем
        self._search_output_schemas[cache_key] = schema
        return schema

    def _build_search_input_schema(
        self, name: str, base: type[BaseModel], model: type
    ) -> type[BaseModel]:
        """Схема для ввода поиска."""
        allowed_fields = list(model.get_all_fields().keys())
        triplets = self._build_search_triplets(base)

        # Защита от пустых списков
        if not allowed_fields:
            allowed_fields = ["id"]

        if not triplets:
            triplets = [Tuple[Literal["id"], Literal["="], int]]

        # Literal требует хотя бы одно значение
        fields_literal = (
            Literal[tuple(allowed_fields)] if len(allowed_fields) > 0 else str
        )
        sort_literal = (
            Literal[tuple(allowed_fields)] if len(allowed_fields) > 0 else str
        )

        return create_model(
            f"{name}SearchInput",
            __config__=ConfigDict(protected_namespaces=()),
            fields=(list[fields_literal], ...),
            end=(Optional[int], None),
            order=(Literal["DESC", "ASC", "desc", "asc"], "DESC"),
            sort=(sort_literal, "id"),
            start=(Optional[int], None),
            limit=(Optional[int], None),
            # filter принимает FilterExpression: список триплетов [field, op, value]
            # и логических операторов 'and'/'or'
            # Пример: [["name", "=", "test"], "or", ["id", ">", 5]]
            filter=(Optional[list[Union[list, Literal["and", "or"]]]], None),
            raw=(bool, False),
        )

    def _build_search_triplets(self, base: type[BaseModel]) -> list:
        """Генерирует типы триплетов для фильтрации.

        JSON не поддерживает tuple, поэтому принимаем list.
        Валидация структуры происходит в filter_parser.py.
        """
        # Собираем все допустимые имена полей и операторы
        triplets = []

        for field_name, field_info in base.model_fields.items():
            metadata = self._get_field_metadata(field_info)

            if metadata and metadata[0] in RELATION_TYPES:
                if metadata[0] in SINGLE_RELATIONS:
                    ops = Literal["=", ">", "<", "!=", ">=", "<="]
                    triplets.append(Tuple[Literal[field_name], ops, Id])
                else:
                    ops = Literal["in", "not in"]
                    triplets.append(Tuple[Literal[field_name], ops, list[Id]])
            else:
                annotation = field_info.annotation
                # Убираем Optional
                if get_origin(annotation) is Union:
                    args = [
                        a for a in get_args(annotation) if a is not type(None)
                    ]
                    if args:
                        annotation = args[0]

                if annotation == str:
                    ops = Literal[
                        "=",
                        "like",
                        "ilike",
                        "=like",
                        "=ilike",
                        "not ilike",
                        "not like",
                    ]
                elif annotation == bool:
                    ops = Literal["=", "!="]
                else:
                    ops = Literal["=", ">", "<", "!=", ">=", "<="]

                triplets.append(Tuple[Literal[field_name], ops, annotation])

        return triplets

    # ==================== Утилиты ====================

    def _transform_relation_for_create(
        self, field_info: FieldInfo, relation_type: type
    ) -> type:
        """Трансформирует поле связи для create/update схемы."""
        if relation_type == Many2one:
            # Many2one -> Id или VirtualId
            base_type = Union[Id, Literal["VirtualId"]]
            if not field_info.is_required():
                return Optional[base_type]
            return base_type

        elif relation_type == PolymorphicMany2one:
            # PolymorphicMany2one -> схема Attachment с опциональными полями
            related = self._get_schema_origin(field_info)

            if (
                related
                and isinstance(related, type)
                and issubclass(related, BaseModel)
            ):
                # Создаём схему с опциональными полями (включая id)
                nested = self._build_attachment_nested_schema(related)
                if not field_info.is_required():
                    return Optional[nested]
                return nested

            # Fallback - если не удалось получить схему
            base_type = Union[Id, Literal["VirtualId"]]
            if not field_info.is_required():
                return Optional[base_type]
            return base_type

        elif relation_type in MANY_RELATIONS:
            # Many2many/One2many -> список операций
            # Получаем Pydantic схему связанной модели
            related = self._get_schema_origin(field_info)

            if (
                related
                and isinstance(related, type)
                and issubclass(related, BaseModel)
            ):
                # Простая схема для вложенных записей (без связей)
                nested = self._build_simple_nested_from_pydantic(related)

                if relation_type == Many2many:
                    wrapper = SchemaRelationMany2ManyUpdateCreate[nested]
                else:
                    wrapper = SchemaRelationOne2ManyUpdateCreate[nested]

                if not field_info.is_required():
                    return Optional[wrapper]
                return wrapper

            # Fallback
            return Optional[list[dict]]

        return field_info.annotation

    def _build_simple_nested_from_pydantic(
        self, pydantic_schema: type[BaseModel]
    ) -> type[BaseModel]:
        """
        Простая вложенная схема без полей Many2many/One2many.
        Используется для create/update.
        """
        cache_key = f"{pydantic_schema.__name__}SimpleNested"

        if cache_key in self._create_schemas:
            return self._create_schemas[cache_key]

        fields = {}

        for field_name, field_info in pydantic_schema.model_fields.items():
            metadata = self._get_field_metadata(field_info)

            # Пропускаем Many2many/One2many (обрубаем рекурсию)
            if metadata and metadata[0] in MANY_RELATIONS:
                continue

            # Many2one оставляем как Id или VirtualId (для связи с родителем при создании)
            if metadata and metadata[0] in SINGLE_RELATIONS:
                fields[field_name] = (
                    Optional[Union[Id, Literal["VirtualId"]]],
                    None,
                )
            else:
                fields[field_name] = (Optional[field_info.annotation], None)

        schema = create_model(
            cache_key, __config__=ConfigDict(protected_namespaces=()), **fields
        )

        self._create_schemas[cache_key] = schema
        return schema

    def _build_attachment_nested_schema(
        self, pydantic_schema: type[BaseModel]
    ) -> type[BaseModel]:
        """
        Схема для PolymorphicMany2one - все поля опциональные включая id.
        Позволяет передавать как id существующего attachment,
        так и данные для создания нового (name, mimetype, size, content и т.д.)
        """
        cache_key = f"{pydantic_schema.__name__}AttachmentNested"

        if cache_key in self._create_schemas:
            return self._create_schemas[cache_key]

        fields = {}

        for field_name, field_info in pydantic_schema.model_fields.items():
            metadata = self._get_field_metadata(field_info)

            # Пропускаем Many2many/One2many (обрубаем рекурсию)
            if metadata and metadata[0] in MANY_RELATIONS:
                continue

            # Many2one оставляем как Id или VirtualId (для связи с родителем при создании)
            if metadata and metadata[0] in SINGLE_RELATIONS:
                fields[field_name] = (
                    Optional[Union[Id, Literal["VirtualId"]]],
                    None,
                )
            else:
                # Все поля опциональные (включая id!)
                fields[field_name] = (Optional[field_info.annotation], None)

        schema = create_model(
            cache_key, __config__=ConfigDict(protected_namespaces=()), **fields
        )

        self._create_schemas[cache_key] = schema
        return schema

    def _get_field_metadata(self, field_info: FieldInfo) -> tuple:
        """Извлекает metadata из поля (для определения типа связи)."""
        from typing import Annotated

        # Сначала проверяем прямой metadata
        if field_info.metadata:
            return field_info.metadata

        # Ищем в аннотации (для Optional и Annotated полей)
        def find_metadata(annotation):
            if annotation is None:
                return ()

            origin = get_origin(annotation)

            # Annotated[X, Many2one] -> (Many2one,)
            if origin is Annotated:
                args = get_args(annotation)
                if len(args) > 1:
                    # Возвращаем всё кроме первого аргумента (типа)
                    return args[1:]
                if args:
                    return find_metadata(args[0])

            # Union[X, None] -> ищем в X
            if origin is Union:
                for arg in get_args(annotation):
                    if arg is not type(None):
                        result = find_metadata(arg)
                        if result:
                            return result

            # Проверяем __metadata__ напрямую
            if hasattr(annotation, "__metadata__"):
                return annotation.__metadata__

            return ()

        return find_metadata(field_info.annotation)

    def _get_schema_origin(self, field_info: FieldInfo) -> type | None:
        """Получает базовый тип схемы (распаковывая Optional, list, Annotated)."""
        from typing import Annotated

        def unwrap(annotation):
            if annotation is None:
                return None

            origin = get_origin(annotation)

            # Annotated[X, ...] -> X
            if origin is Annotated:
                args = get_args(annotation)
                if args:
                    return unwrap(args[0])

            # Union[X, None] -> X
            if origin is Union:
                for arg in get_args(annotation):
                    if arg is not type(None):
                        return unwrap(arg)

            # list[X] -> X
            if origin is list:
                args = get_args(annotation)
                if args:
                    return unwrap(args[0])

            # Если это класс - возвращаем
            if isinstance(annotation, type):
                return annotation

            return annotation

        return unwrap(field_info.annotation)

    def _get_default(self, field_info: FieldInfo) -> Any:
        """Получает default значение для поля."""
        if field_info.is_required():
            return ...
        return None


# Глобальный инстанс
schema_registry = SchemaRegistry()
