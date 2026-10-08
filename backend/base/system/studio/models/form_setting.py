"""
Общие настройки формы модели: какие поля обязательны и какие поля вне
разметки формы показывать в зоне «Дополнительно» — где она стоит (под
формой, колонкой справа, вкладкой) и как поля разложены по её сетке.

Одна запись на модель, общая для всех пользователей — задаёт администратор
настроек в режиме студии. Обязательность здесь уровня интерфейса, как
Required у поля в Odoo Studio: форма ставит звёздочку и не даёт сохранить
пустое, а API и код (входящие сообщения, импорт, крон) её не проверяют —
иначе автосоздание партнёра из входящего без ИНН падало бы.
"""

import json
from typing import Any, Self

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.decorators import constrains
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Selection,
    Text,
)
from backend.base.system.dotorm.dotorm.model import DotModel


def _json_list(raw: str | None) -> list:
    """JSON-массив; не массив — 400."""
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except ValueError:
        items = None
    if not isinstance(items, list):
        raise FaraException(
            {"content": "FORM_SETTING_INVALID_JSON", "status_code": 400}
        )
    return items


def _is_cell(item: Any) -> bool:
    """Клетка зоны: {"name": str}, x/y/w/h — целые от 1, необязательные."""
    if not isinstance(item, dict) or not isinstance(item.get("name"), str):
        return False
    return all(
        isinstance(item.get(key, 1), int) and item.get(key, 1) >= 1
        for key in ("x", "y", "w", "h")
    )


def _field_names(raw: str | None) -> list[str]:
    """Имена полей из JSON-массива строк; иначе 400."""
    names = _json_list(raw)
    if not all(isinstance(name, str) for name in names):
        raise FaraException(
            {"content": "FORM_SETTING_INVALID_JSON", "status_code": 400}
        )
    return names


def _cell_names(raw: str | None) -> list[str]:
    """Имена полей из JSON-массива клеток зоны; иначе 400."""
    cells = _json_list(raw)
    if not all(_is_cell(cell) for cell in cells):
        raise FaraException(
            {"content": "FORM_SETTING_INVALID_JSON", "status_code": 400}
        )
    return [cell["name"] for cell in cells]


class FormSetting(DotModel):
    """Общие настройки формы модели."""

    __table__ = "form_settings"

    id: int = Integer(primary_key=True)

    # Модель — имя таблицы, как в адресе формы (partners, leads).
    model_name: str = Char(required=True, unique=True)

    # Только хранимые поля (скаляры и Many2one): поле-таблицу (One2many,
    # Many2many) форма без разметки колонок не нарисует.
    # JSON-массив имён обязательных в форме полей.
    required: str | None = Text()
    # JSON-массив клеток зоны «Дополнительно» — поля, которых нет в
    # разметке формы: {"name", "x", "y", "w", "h"} — колонка и строка
    # левого верхнего угла и размер в клетках, всё с 1. Без x/y поле
    # встаёт в первую свободную клетку.
    extra_fields: str | None = Text()

    # Где зона: под формой, колонкой справа от неё или вкладкой (у формы
    # без вкладок — под формой).
    extra_placement: str = Selection(
        options=[("bottom", "Bottom"), ("side", "Side"), ("tab", "Tab")],
        default="bottom",
        default_db=True,
    )
    # Сетка зоны: колонок; строк — пусто, если сколько понадобится.
    extra_columns: int = Integer(default=1, default_db=True)
    extra_rows: int | None = Integer()

    @constrains("extra_columns", "extra_rows")
    async def _constrains_grid(self, records: list[Self]) -> None:
        """Сетка — от одной клетки; иначе 400."""
        for record in records:
            for value in (record.extra_columns, record.extra_rows):
                if value is not None and value < 1:
                    raise FaraException(
                        {
                            "content": "FORM_SETTING_BAD_GRID",
                            "detail": str(value),
                            "status_code": 400,
                        }
                    )

    @constrains("model_name", "required", "extra_fields")
    async def _constrains_known_fields(self, records: list[Self]) -> None:
        """Имена — хранимые публичные поля модели; иначе 400."""
        for record in records:
            # На update модель в payload не приходит — дочитать.
            if not record.is_assigned("model_name"):
                stored = await self.sudo().search_one(
                    filter=[("id", "=", record.id)], fields=["model_name"]
                )
                record.model_name = stored.model_name
            try:
                model = env.models._get_model_class_by_table(record.model_name)
            except KeyError:
                raise FaraException(
                    {
                        "content": "FORM_SETTING_UNKNOWN_MODEL",
                        "detail": record.model_name,
                        "status_code": 400,
                    }
                )
            fields = model.get_public_fields()
            names = _field_names(record.required) + _cell_names(
                record.extra_fields
            )
            for name in names:
                field = fields.get(name)
                if field is None or not field.store:
                    raise FaraException(
                        {
                            "content": "FORM_SETTING_UNKNOWN_FIELD",
                            "detail": name,
                            "status_code": 400,
                        }
                    )
