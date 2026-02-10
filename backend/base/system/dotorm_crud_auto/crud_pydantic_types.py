"""
Этот модуль содержит pydantic классы,
которые позволяют динамически изменять уже существующие pydantic модели.
Используется для автоматической генерации схем валидации в crud routes.
"""

from typing import (
    Any,
    Literal,
    Optional,
    Tuple,
    Type,
    Union,
    get_origin,
    get_args,
    Annotated,
)

from pydantic import BaseModel, ConfigDict, Field
from pydantic_core import PydanticUndefined

from backend.base.system.dotorm_crud_auto.crud_pydantic_schemas import (
    SchemaRelationNested,
    SchemaSearchOutput,
    SchemaRelationMany2ManyUpdateCreate,
    SchemaRelationOne2ManyUpdateCreate,
)
from backend.base.system.dotorm.dotorm.fields import (
    PolymorphicMany2one,
    PolymorphicOne2many,
    Many2many,
    Many2one,
    One2many,
)
from backend.base.system.schemas.base_schema import Id


def get_schema_origin(field: Field):  # type: ignore
    """
    Получить базовый тип схемы из аннотации поля.
    Рекурсивно распаковывает Annotated, Optional, Union и list.
    """

    def unwrap(annotation):
        origin = get_origin(annotation)

        # Распаковываем Optional/Union
        if origin is Union:
            args = get_args(annotation)
            for arg in args:
                if arg is not type(None):
                    return unwrap(arg)

        # Распаковываем Annotated
        if origin is Annotated:
            args = get_args(annotation)
            if args:
                return unwrap(args[0])

        # Распаковываем list
        if origin is list:
            args = get_args(annotation)
            if args:
                return unwrap(args[0])

        return annotation

    return unwrap(field.annotation)


def get_field_metadata(field) -> tuple:
    """
    Возвращает metadata поля. Если field.metadata пустая,
    пытается извлечь из вложенной аннотации (для Optional полей).
    """
    if field.metadata:
        return field.metadata

    # Ищем в аннотации
    def find_in_annotation(annotation):
        origin = get_origin(annotation)

        if origin is Annotated:
            args = get_args(annotation)
            if len(args) > 1:
                return args[1:]
            return find_in_annotation(args[0])

        if origin is Union:
            for arg in get_args(annotation):
                if arg is not type(None):
                    result = find_in_annotation(arg)
                    if result:
                        return result
        return ()

    return find_in_annotation(field.annotation)


def create_class(name, *inherits):
    import types

    def exec_body(ns):
        ns["model_config"] = ConfigDict(protected_namespaces=())

    NewClass = types.new_class(name, inherits, exec_body=exec_body)
    return NewClass


#  # Создаем новую модель с обновленными полями
#     return type(
#         f"Partial{cls.__name__}",
#         (BaseModel,),
#         {
#             **new_fields,
#             "__module__": cls.__module__
#         }
#     )


# def to_optional_fields(model: Type[BaseModel], generated_models={}):
#     # if not generated_models:
#     # generated_models = {model.__name__ + "RelationNestedUpdate": None}
#     new_fields = {}
#     for field_name, field in model.model_fields.items():
#         # если найдено поле m2o
#         if field.metadata and field.metadata[0] in [Many2one, One2many, Many2many]:
#             if field.metadata[0] == Many2one:
#                 new_annotation = Union[Id, Literal["VirtualId"]]
#                 if not field.is_required():
#                     new_annotation = Optional[field.annotation]
#                 new_fields[field_name] = (new_annotation, None)

#             elif field.annotation:
#                 # TODO: придумать что то с бесконечной вложенностью
#                 # скоерй всего заменить на идишник во втором вложении
#                 # как при чтении, хотя это не совсем корректное создание
#                 # тогда вложенные созадуться а эти нет)
#                 # получить схему
#                 schema_origin = get_schema_origin(field)
#                 # TODO: приумать что-то с бесконечной рекурсией
#                 if schema_origin:
#                     # if (
#                     #     schema_origin.__name__ + "RelationNestedUpdate"
#                     #     in generated_models
#                     #     # and generated_models[
#                     #     #     schema_origin.__name__ + "RelationNestedUpdate"
#                     #     # ]
#                     #     # != None
#                     # ):
#                     #     new_fields[field_name] = generated_models[
#                     #         schema_origin.__name__ + "RelationNestedUpdate"
#                     #     ]
#                     #     continue
#                     if field.metadata[0] == Many2many:
#                         # schema_relation_update = create_class(
#                         #     schema_origin.__name__ + "RelationNestedCreate",
#                         #     schema_origin,
#                         #     Partial,
#                         #     OmitId,
#                         #     RelationNestedCreate,
#                         # )
#                         fields = to_optional_fields(schema_origin, generated_models)
#                         schema_relation_update = create_model(
#                             schema_origin.__name__ + "RelationNestedUpdate",
#                             **fields,
#                         )
#                         new_annotation = SchemaRelationMany2ManyUpdateCreate[
#                             schema_relation_update
#                         ]
#                         if not field.is_required():
#                             new_annotation = Optional[new_annotation]
#                         new_fields[field_name] = (new_annotation, None)
#                         # generated_models[
#                         #     schema_origin.__name__ + "RelationNestedUpdate"
#                         # ] = new_annotation

#                     if field.metadata[0] == One2many:
#                         # schema_relation_update = create_class(
#                         #     schema_origin.__name__ + "RelationNestedCreate",
#                         #     schema_origin,
#                         #     Partial,
#                         #     OmitId,
#                         #     RelationNestedCreate,
#                         # )
#                         fields = to_optional_fields(schema_origin, generated_models)
#                         schema_relation_update = create_model(
#                             schema_origin.__name__ + "RelationNestedUpdate",
#                             **fields,
#                         )
#                         new_annotation = SchemaRelationOne2ManyUpdateCreate[
#                             schema_relation_update
#                         ]
#                         if not field.is_required():
#                             new_annotation = Optional[new_annotation]
#                         new_fields[field_name] = (new_annotation, None)
#                         # generated_models[
#                         #     schema_origin.__name__ + "RelationNestedUpdate"
#                         # ] = new_annotation
#     return new_fields


class RelationNested(BaseModel):
    """Класс менят схему полей связей. Используется в схеме обновления"""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        for field in list(cls.model_fields.values()):
            # если найдено поле m2o
            metadata = get_field_metadata(field)
            if metadata and metadata[0] in [
                Many2one,
                One2many,
                Many2many,
                PolymorphicOne2many,
                PolymorphicMany2one,
            ]:
                if metadata[0] == Many2one:
                    field.annotation = Union[Id, Literal["VirtualId"]]  # type: ignore
                    if not field.is_required():
                        field.annotation = Optional[field.annotation]  # type: ignore
                elif metadata[0] == PolymorphicMany2one:
                    # Для PolymorphicMany2one создаём схему где id опционален
                    schema_origin = get_schema_origin(field)
                    if schema_origin and hasattr(schema_origin, "__schema__"):
                        # Преобразуем DotModel в Pydantic схему
                        pydantic_schema = schema_origin.__schema__
                        schema_relation_update = create_class(
                            pydantic_schema.__name__ + "RelationNestedCreate",
                            pydantic_schema,
                            Partial,  # делает все поля опциональными, включая id
                            # НЕ используем OmitId — id должен остаться!
                            RelationNested,
                        )
                        field.annotation = schema_relation_update
                        if not field.is_required():
                            field.annotation = Optional[field.annotation]  # type: ignore
                elif field.annotation:
                    # TODO: придумать что то с бесконечной вложенностью
                    # Проблема. Существуют модели которые ссылаются друг на друга
                    # например roles и users они имеют отношение многие ко многим.
                    # соответственно алгоритм входит в бесконечную рекурсию когда пытаемся
                    # изменить поля моделей на поля которые нужны для создания
                    schema_origin = get_schema_origin(field)
                    if schema_origin:
                        if metadata[0] == Many2many:
                            schema_relation_update = create_class(
                                schema_origin.__name__
                                + "RelationNestedCreate",
                                schema_origin,
                                Partial,
                                OmitId,
                                # TODO: надо сделать так чтобы работала рекурсия
                                # пока просто на 3 вложенности удаляем поля связи тем самым
                                # прекращая рекурсию
                                RelationOmitX2M,
                                # RelationNestedPickIdName,
                                # RelationNestedCreate,
                            )
                            field.annotation = (
                                SchemaRelationMany2ManyUpdateCreate[
                                    schema_relation_update
                                ]
                            )
                            if not field.is_required():
                                field.annotation = Optional[field.annotation]  # type: ignore

                        if metadata[0] in [One2many, PolymorphicOne2many]:
                            schema_relation_update = create_class(
                                schema_origin.__name__
                                + "RelationNestedCreate",
                                schema_origin,
                                Partial,
                                OmitId,
                                # TODO: надо сделать так чтобы работала рекурсия
                                # пока просто на 3 вложенности удаляем поля связи тем самым
                                # прекращая рекурсию
                                RelationOmitX2M,
                                # RelationNestedPickIdName,
                                # RelationNestedCreate,
                            )
                            field.annotation = (
                                SchemaRelationOne2ManyUpdateCreate[
                                    schema_relation_update
                                ]
                            )
                            if not field.is_required():
                                field.annotation = Optional[field.annotation]  # type: ignore


class RelationNestedUpdateCreate(BaseModel):
    """Класс менят схему полей связей при обновлении и создании"""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)

        for field in list(cls.model_fields.values()):
            metadata = get_field_metadata(field)

            # если найдено поле связи
            if metadata and metadata[0] in [
                Many2one,
                Many2many,
                One2many,
                PolymorphicOne2many,
                PolymorphicMany2one,
            ]:
                # if field.metadata[0] in [Many2one, PolymorphicMany2one]:
                if metadata[0] == Many2one:
                    # class_type = field.annotation
                    field.annotation = Union[Id, Literal["VirtualId"]]  # type: ignore
                    if not field.is_required():
                        field.annotation = Optional[field.annotation]  # type: ignore

                elif metadata[0] == PolymorphicMany2one:
                    # Для PolymorphicMany2one создаём схему где id опционален
                    schema_origin = get_schema_origin(field)
                    if schema_origin and hasattr(schema_origin, "__schema__"):
                        # Преобразуем DotModel в Pydantic схему
                        pydantic_schema = schema_origin.__schema__
                        schema_relation_update = create_class(
                            pydantic_schema.__name__ + "RelationNestedUpdate",
                            pydantic_schema,
                            Partial,  # делает все поля опциональными, включая id
                            # НЕ используем OmitId — id должен остаться!
                            RelationNested,
                        )
                        field.annotation = schema_relation_update
                        if not field.is_required():
                            field.annotation = Optional[field.annotation]  # type: ignore

                elif field.annotation:
                    # получить схему
                    schema_origin = get_schema_origin(field)
                    # TODO: придумать что-то с бесконечной рекурсией
                    if schema_origin:
                        if metadata[0] == Many2many:
                            schema_relation_update = create_class(
                                schema_origin.__name__
                                + "RelationNestedUpdate",
                                schema_origin,
                                Partial,
                                OmitId,
                                RelationNested,
                            )
                            # fields = to_optional_fields(schema_relation_update)
                            # schema_relation_update = create_model(
                            #     schema_origin.__name__ + "RelationNestedUpdate",
                            #     **fields,
                            # )

                            field.annotation = (
                                SchemaRelationMany2ManyUpdateCreate[
                                    schema_relation_update
                                ]
                            )
                            if not field.is_required():
                                field.annotation = Optional[field.annotation]  # type: ignore

                        if metadata[0] in [One2many, PolymorphicOne2many]:
                            schema_relation_update = create_class(
                                schema_origin.__name__
                                + "RelationNestedUpdate",
                                schema_origin,
                                Partial,
                                OmitId,
                                RelationNested,
                            )
                            # fields = to_optional_fields(schema_relation_update)
                            # schema_relation_update = create_model(
                            #     schema_origin.__name__ + "RelationNestedUpdate",
                            #     **fields,
                            # )
                            field.annotation = (
                                SchemaRelationOne2ManyUpdateCreate[
                                    schema_relation_update
                                ]
                            )
                            if not field.is_required():
                                field.annotation = Optional[field.annotation]  # type: ignore

        cls.model_rebuild(force=True)


class RelationNestedSearch(BaseModel):
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Работает в форме (read). Используется в ручке search на выход.
        Класс изменяет вложенные (nested) поля связей,
        внутри полей связи текущей схемы.
        Это используется на 2 уровне вложенности моделей так как:
        1. Бесконечно отображать все вложенные модели нет необходимости.
        2. Если модели ссылаются друг на друга могут быть бесконечные вложенности.
        Для изменения уже существующего пидантик класса.
        """
        super().__pydantic_init_subclass__(**kwargs)

        for field in list(cls.model_fields.values()):
            # если найдено поле связи
            if field.annotation and field.metadata:
                # получить схему
                schema_origin = get_schema_origin(field)
                if schema_origin:
                    if field.metadata[0] in [
                        Many2one,
                        Many2many,
                        One2many,
                        PolymorphicOne2many,
                        PolymorphicMany2one,
                    ]:
                        # изменить схему "обрубив" вложенные модели связей
                        schema = create_class(
                            schema_origin.__name__ + "NestedPartial",
                            schema_origin,
                            Partial,
                            RelationNestedPickIdName,
                        )
                        if field.metadata[0] in [
                            Many2many,
                            One2many,
                            PolymorphicOne2many,
                        ]:
                            # тут добавить вывод информации о полей
                            field.annotation = SchemaSearchOutput[list[schema]]
                        else:
                            field.annotation = schema

        cls.model_rebuild(force=True)


class RelationNestedPickIdName(BaseModel):
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Работает для списка(search) и для формы(get) на вывод.
        Класс оставляет только поля id и name (SchemaRelationNested) у полей связи
        тем самым прекращая рекурсию вложенных моделей"""
        super().__pydantic_init_subclass__(**kwargs)

        for field in list(cls.model_fields.values()):
            # если найдено поле связи
            if field.metadata and field.metadata[0] in [
                Many2one,
                Many2many,
                One2many,
                PolymorphicOne2many,
                PolymorphicMany2one,
            ]:
                if field.metadata[0] in [Many2one, PolymorphicMany2one]:
                    # сделать поля не обязательными
                    field.default = None
                    field.annotation = Union[SchemaRelationNested, None]  # type: ignore
                else:
                    # сделать поля не обязательными
                    field.default = None
                    field.annotation = Union[list[SchemaRelationNested], None]  # type: ignore

        cls.model_rebuild(force=True)


class RelationOmitX2M(BaseModel):
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Удаляет все поля m2m и o2m в модели"""
        super().__pydantic_init_subclass__(**kwargs)

        for name, field in list(cls.model_fields.items()):
            # если найдено поле связи m2m или o2m
            if field.metadata and field.metadata[0] in [
                Many2many,
                One2many,
                PolymorphicOne2many,
            ]:
                # field.default = PydanticUndefined
                del cls.model_fields[name]
        cls.model_rebuild(force=True)


class Partial(BaseModel):
    """Класс делает все поля модели опциональными
    Для изменения уже существующего пидантик класса."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)

        # __pydantic_fields__.values()
        for field in list(cls.model_fields.values()):
            # if field.is_required():
            field.default = None
            field.annotation = Union[field.annotation, None]  # type: ignore

        cls.model_rebuild(force=True)


class OmitId(BaseModel):
    """Класс исключает поле id из модели
    Для изменения уже существующего пидантик класса."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)

        for name, field in list(cls.model_fields.items()):
            if name == "id":
                field.default = PydanticUndefined
                del cls.model_fields[name]

        cls.model_rebuild(force=True)


def generate_search_triplet(model: Type[BaseModel]):
    """Генерирует схему возможных триплетов поиска (фильтра) для ручки поиска."""
    res = []
    for name, field in list(model.model_fields.items()):
        # Получаем metadata правильным способом (для Optional полей)
        metadata = get_field_metadata(field)

        # если найдено поле связи
        if metadata and metadata[0] in [
            Many2many,
            One2many,
            Many2one,
            PolymorphicOne2many,
            PolymorphicMany2one,
        ]:
            allowed_operator = Literal["in", "not in"]
            field_model = Tuple[Literal[name], allowed_operator, list[Id]]
            if metadata[0] in [Many2one, PolymorphicMany2one]:
                allowed_operator = Literal["=", ">", "<", "!=", ">=", "<="]
                field_model = Tuple[Literal[name], allowed_operator, Id]
            res.append(field_model)
        else:
            if field.annotation == str:
                allowed_operator = Literal[
                    "=",
                    "like",
                    "ilike",
                    "=like",
                    "=ilike",
                    "not ilike",
                    "not like",
                ]
            elif field.annotation == bool:
                allowed_operator = Literal["=", "!="]
            elif (
                field.annotation == int
                or field.annotation == float
                or field.annotation in [Many2one, PolymorphicMany2one]
            ):
                allowed_operator = Literal["=", ">", "<", "!=", ">=", "<="]
            else:  # or field.annotation == datetime
                allowed_operator = Literal["=", ">", "<", "!=", ">=", "<="]

            field_model = Tuple[
                Literal[name], allowed_operator, field.annotation
            ]

            res.append(field_model)
    return res
