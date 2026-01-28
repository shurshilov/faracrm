try:
    from pydantic import create_model, ConfigDict
    from pydantic.fields import Field
except:
    print("pydantic lib not installed")
from types import UnionType
from typing import Any, List, Literal, Optional, Type, TypeAlias, Union


from ..fields import (
    Many2many,
    One2many,
    Field as DotField,
)


def dotorm_to_pydantic_nested_one(cls):
    """Работает с моделями DotOrm.
    Которая возвращает все поля модели.
    Используется на вход get и create_default
    Прерывается на первом уровне вложенности"""
    fields_store = []
    fields_relation = []

    # Используем get_all_fields() чтобы получить поля включая добавленные через @extend
    for field_name, field in cls.get_all_fields().items():
        if isinstance(field, DotField):
            if not isinstance(field, (Many2many, One2many)):
                fields_store.append(field_name)

            else:
                # если это поле множественной связи m2m или o2m
                # то это поле будет содержать просто список своих полей
                allowed_fields = list(field.relation_table.get_all_fields())
                # TODO: по идее должно быть так
                # relation_table = field.relation_table
                # if callable(relation_table):
                #     relation_table = relation_table()
                # allowed_fields = list(relation_table.get_all_fields())
                params = {field_name: (list[Literal[*allowed_fields]], ...)}
                SchemaGetFieldRelationInput = create_model(
                    "SchemaGetFieldRelationInput",
                    **params,
                    # field_name=(list[Literal[*allowed_fields]], ...),
                )
                fields_relation.append(SchemaGetFieldRelationInput)

    return create_model(
        "SchemaGetInput",
        fields=(list[Union[Literal[*fields_store], *fields_relation]], ...),
    )


from typing import (
    Annotated,
    get_type_hints,
    ForwardRef,
    Union,
    get_args,
    get_origin,
)
from pydantic import BaseModel, Field, create_model


def replace_custom_types(py_type, class_map: dict[str, Type[BaseModel]]):
    """
    Рекурсивно заменяет кастомные типы на SchemaXXX,
    поддерживает строковые аннотации:
        - "Uom"
        - "Uom | None"
        - "Role | None | Attachment"
    """
    # --- строковый тип ---
    if isinstance(py_type, str):
        # 2) обычная строка: "Uom"
        return ForwardRef(f"Schema{py_type}")

    # --- обычный Union ---
    origin = get_origin(py_type)
    args = get_args(py_type)

    if origin is UnionType and args:
        return Union[
            tuple(replace_custom_types(arg, class_map) for arg in args)
        ]

    # --- список ---
    if origin in (list, List) and args:
        return list[replace_custom_types(args[0], class_map)]

    # --- кастомный класс ---
    if hasattr(py_type, "__name__"):
        name = py_type.__name__
        if name in class_map:
            return ForwardRef(f"Schema{name}")

    return py_type


def convert_field_type(
    py_type, field_value, class_map: dict[str, Type[BaseModel]]
):
    """
    Оборачиваем тип в Annotated и корректно обрабатываем None.
    """
    final_type = replace_custom_types(py_type, class_map)

    # --- определяем, допускает ли поле None ---
    allows_none = False

    # 1) строковая аннотация: "Uom | None"
    if isinstance(py_type, str) and "None" in py_type:
        allows_none = True

    # 2) обычный Python union: Role | None
    elif get_origin(py_type) is UnionType and type(None) in get_args(py_type):
        allows_none = True

    # --- обёртка Annotated ---
    if field_value is not None:
        annotated = Annotated[final_type, field_value.__class__]

        # optional?
        if allows_none:
            return Optional[annotated]

        return annotated

    return final_type


def generate_pydantic_models(
    classes: list[type], prefix="Schema"
) -> dict[str, type[BaseModel]]:
    known_models: dict[str, type[BaseModel]] = {}
    pending_fields: dict[str, dict] = {}

    # Сначала создаем "пустые оболочки" моделей, чтобы можно было ссылаться на них
    for cls in classes:
        model_name = f"{prefix}{cls.__name__}"
        model = create_model(
            model_name,
            # __base__=BaseModel,
            __config__=ConfigDict(protected_namespaces=()),
        )
        known_models[cls.__name__] = model
        pending_fields[cls.__name__] = {}

    # Теперь наполняем поля
    for cls in classes:
        cls_name = cls.__name__

        # Используем get_all_fields() для получения всех полей включая @extend
        all_fields = cls.get_all_fields()

        # Собираем аннотации из всех классов в MRO + добавленные через @extend
        annotations = {}
        for klass in reversed(cls.__mro__):
            if klass is object:
                continue
            annotations.update(getattr(klass, "__annotations__", {}))

        # Добавляем аннотации для полей из @extend которые могут не иметь __annotations__
        for field_name, field_obj in all_fields.items():
            if field_name not in annotations:
                # Получаем тип из Field объекта
                if hasattr(field_obj, "python_type"):
                    annotations[field_name] = field_obj.python_type
                else:
                    # Fallback - используем Any
                    annotations[field_name] = Any

        model_fields = {}

        for name, py_type in annotations.items():
            # Проверяем что это реально поле модели
            if name not in all_fields:
                continue

            field_value = all_fields.get(name)

            # Разрешаем ForwardRef или вложенные типы
            final_type = convert_field_type(py_type, field_value, known_models)

            if isinstance(field_value, DotField):
                # Используем метод модели для определения обязательности
                is_required = cls._is_field_required(name, field_value)
                required = Ellipsis if is_required else None

                # если есть значение по умолчанию
                if field_value.default is not None:
                    # если default callable — вызываем
                    if callable(field_value.default):
                        default: Any = field_value.default()
                    else:
                        default = field_value.default
                    # необходимо проставить через json_schema_extra чтобы поле осталось
                    # обязательным, но с default по умолчанию любое default делает поле
                    # не обязательным прихожится обходить это для более интуитивной работы
                    # отделить значение по умолчанию и обязательность поля
                    default = Field(
                        required, json_schema_extra={"default": default}
                    )
                else:
                    # нет default значит поле обязательное
                    default = required

                model_fields[name] = (final_type, default)

        # Обновляем модель
        model_name = f"{prefix}{cls_name}"
        known_models[cls_name] = create_model(
            model_name,
            # __base__=known_models[cls_name],
            **model_fields,
            __config__=ConfigDict(protected_namespaces=(), frozen=False),
        )

    # Обновляем forward refs
    _types_namespace = {
        f"Schema{name}": model for name, model in known_models.items()
    }
    for model in known_models.values():
        model.model_rebuild(force=True, _types_namespace=_types_namespace)

    return known_models
