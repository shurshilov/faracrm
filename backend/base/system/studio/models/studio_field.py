"""
Поля студии: колонки, которые администратор настроек добавляет к модели из
интерфейса, без кода.

Описание лежит здесь, значения — в обычной колонке таблицы модели: поле
вешается на модель на старте (StudioApp.refresh) и дальше неотличимо от
объявленного в коде — его видят список, форма, фильтры, экспорт и API.

Имя — техническое, с префиксом x_ (как у Odoo): не пересечётся с полями
ядра, и сразу видно, откуда поле. Тип и имя после создания не меняются —
поле создаётся заново. Удаление снимает поле с модели, колонка и данные
остаются (роутер studio): поле с тем же именем и типом, созданное снова,
получит прежние значения.
"""

import datetime
import json
import re
from typing import Self

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.decorators import constrains
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Date,
    Datetime,
    Field,
    Float,
    Integer,
    Many2one,
    Selection,
    Text,
)
from backend.base.system.dotorm.dotorm.model import DotModel

# Тип поля студии → класс поля dotorm и аннотация для API-схем. У связи
# (many2one) аннотация — строка с именем класса связанной модели, так её
# резолвит генератор схем (см. core/extensions._apply_annotation).
FIELD_TYPES: dict[str, tuple[type[Field], object]] = {
    "char": (Char, str | None),
    "text": (Text, str | None),
    "integer": (Integer, int | None),
    "float": (Float, float | None),
    "boolean": (Boolean, bool | None),
    "date": (Date, datetime.date | None),
    "datetime": (Datetime, datetime.datetime | None),
    "selection": (Selection, str | None),
    "many2one": (Many2one, None),
}

NAME_RE = re.compile(r"^x_[a-z][a-z0-9_]*$")
# Предел имени идентификатора Postgres.
NAME_MAX_LENGTH = 63


def _error(content: str, detail: str | None = None) -> FaraException:
    return FaraException(
        {"content": content, "detail": detail, "status_code": 400}
    )


class StudioField(DotModel):
    """Поле модели, добавленное из интерфейса."""

    __table__ = "studio_fields"
    # Создание и удаление — только через роутер студии: кроме строки нужны
    # колонка в таблице и пересборка схем API (routers/studio.py).
    __auto_crud__ = False

    id: int = Integer(primary_key=True)

    # Таблица модели, как в адресе формы (partners, leads).
    model_name: str = Char(required=True)
    # Техническое имя колонки: x_ + латиница, цифры, подчёркивание.
    name: str = Char(max_length=NAME_MAX_LENGTH, required=True)
    # Подпись в интерфейсе (Field.string).
    label: str = Char(required=True)
    field_type: str = Selection(
        options=[
            ("char", "Строка"),
            ("text", "Текст"),
            ("integer", "Целое число"),
            ("float", "Число"),
            ("boolean", "Флажок"),
            ("date", "Дата"),
            ("datetime", "Дата и время"),
            ("selection", "Выбор из списка"),
            ("many2one", "Ссылка на запись"),
        ],
        required=True,
    )
    # JSON-массив пар [значение, подпись] — только у выбора из списка.
    options: str | None = Text()
    # Таблица связанной модели — только у ссылки на запись.
    relation_model: str | None = Char()

    @staticmethod
    def _model(table: str | None) -> type[DotModel]:
        try:
            return env.models._get_model_class_by_table(table or "")
        except KeyError:
            raise _error("STUDIO_FIELD_BAD_MODEL", table)

    @staticmethod
    def _options(raw: str | None) -> list[tuple[str, str]]:
        """Варианты выбора из JSON: непустой список пар строк, значения
        без повторов; иначе 400."""
        try:
            pairs = json.loads(raw or "")
        except ValueError:
            pairs = None
        ok = (
            isinstance(pairs, list)
            and pairs
            and all(
                isinstance(pair, list)
                and len(pair) == 2
                and all(isinstance(item, str) and item for item in pair)
                for pair in pairs
            )
        )
        if not ok or len({value for value, _ in pairs}) != len(pairs):
            raise _error("STUDIO_FIELD_BAD_OPTIONS")
        return [(value, label) for value, label in pairs]

    @constrains(
        "model_name", "name", "field_type", "options", "relation_model"
    )
    async def _constrains_definition(self, records: list[Self]) -> None:
        """Модель известна, имя по правилу и свободно, тип из списка,
        варианты и связанная модель заданы там, где нужны; иначе 400.
        На update меняются только подпись и варианты (роутер studio) —
        проверяем варианты по сохранённому типу."""
        for record in records:
            if record.id:
                stored = await self.sudo().search_one(
                    filter=[("id", "=", record.id)], fields=["field_type"]
                )
                if stored.field_type == "selection" and record.is_assigned(
                    "options"
                ):
                    self._options(record.options)
                continue
            model = self._model(record.model_name)
            if not NAME_RE.match(record.name or ""):
                raise _error("STUDIO_FIELD_BAD_NAME", record.name)
            # Занято полем из кода или уже применённым полем студии.
            if record.name in model.get_fields():
                raise _error("STUDIO_FIELD_EXISTS", record.name)
            # Строка другого воркера, ещё не применённая здесь.
            if await self.sudo().search_count(
                filter=[
                    ("model_name", "=", record.model_name),
                    ("name", "=", record.name),
                ]
            ):
                raise _error("STUDIO_FIELD_EXISTS", record.name)
            if record.field_type not in FIELD_TYPES:
                raise _error("STUDIO_FIELD_BAD_TYPE", record.field_type)
            if record.field_type == "selection":
                self._options(record.options)
            if record.field_type == "many2one":
                self._model(record.relation_model)

    def build(self) -> tuple[Field, object]:
        """Поле dotorm и аннотация для API-схем по описанию."""
        field_cls, annotation = FIELD_TYPES[self.field_type]
        if self.field_type == "selection":
            field = Selection(
                options=self._options(self.options), string=self.label
            )
        elif self.field_type == "many2one":
            related = self._model(self.relation_model)
            field = Many2one(related, string=self.label)
            annotation = f"{related.__name__} | None"
        elif self.field_type == "boolean":
            field = Boolean(default=False, string=self.label)
        else:
            field = field_cls(string=self.label)
        return field, annotation
