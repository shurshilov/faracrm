"""
Этот модуль содержит статические схемы валидации.
Используется для автоматической генерации схем валидации в crud routes.
"""

from pydantic import BaseModel

from backend.base.system.schemas.base_schema import Id


class GetListField(BaseModel):
    "Используется при чтении множества записей"

    name: str
    type: str
    relation: str | None = None
    options: list | None = None  # Добавлено для совместимости
    required: bool = False


class GetFormField(BaseModel):
    "Используется при чтении одиночной записи или значений по умолчанию"

    name: str
    type: str
    relatedModel: str | None = None
    relatedField: str | None = None
    options: list | None = None
    relation: str | None = None  # Добавлено для совместимости с вложенными
    required: bool = False


class SchemaSearchOutput[Model](BaseModel):
    "Используется при чтении множества записей"

    data: Model
    total: int | None = None
    fields: list[GetListField]


class SchemaGetOutput[Model](BaseModel):
    "Используется при чтении одиночной записи или значений по умолчанию"

    data: Model
    fields: dict[str, GetFormField]


class SchemaCreateOutput(BaseModel):
    "Используется при создании записи, возвращается ид созданной записи"

    id: int


# class SchemaRelationFieldsInfo[Model](BaseModel):
#     data: Model
#     fields: list[GetListField]
#     total: int | None = None


class SchemaRelationNested(BaseModel):
    """Используется при чтении одиночной записи или мнодества записей.
    Оставляя на каком-либо уровне вложенности только id и name поля"""

    id: Id
    name: str


class SchemaRelationMany2ManyUpdateCreate[Model](BaseModel):
    """Используется при обновлении или создании одиночной записи.
    Для полей отношений m2m.
    Позволяя за один запрос сразу добавить связанные записи."""

    created: list[Model] = []
    deleted: list[Id] = []
    selected: list[Id] = []
    unselected: list[Id] = []


class SchemaRelationOne2ManyUpdateCreate[Model](BaseModel):
    """Используется при обновлении или создании одиночной записи.
    Для полей отношений o2m.
    Позволяя за один запрос сразу добавить связанные записи."""

    created: list[Model] = []
    deleted: list[Id] = []
