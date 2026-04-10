# Copyright 2025 FARA CRM
# Core module - onchange router

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.fields import (
    Many2one,
    PolymorphicMany2one,
)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.system.dotorm.dotorm.fields import Field


router_private = APIRouter(
    tags=["Onchange"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


def _hydrate_m2o_values(
    values: dict[str, Any],
    fields: dict[str, "Field"],
) -> None:
    """
    Рекурсивно конвертирует M2O значения из dict в экземпляры моделей.

    Фронт присылает M2O как dict: {id: 5, name: "Widget", uom_id: {id: 3, name: "кг"}}.
    Конструктор DotModel просто делает setattr — не конвертирует.
    Эта функция превращает dict в Product(id=5, name="Widget", uom_id=Uom(id=3, ...)).

    Работает in-place, без запросов к БД — все данные из фронтенда.
    """
    for field_name, field_class in fields.items():
        if field_name not in values:
            continue
        if not isinstance(field_class, (Many2one, PolymorphicMany2one)):
            continue

        val = values[field_name]
        related_model = field_class.relation_table
        if related_model:
            # Рекурсия: вложенные M2O внутри dict
            related_fields = related_model.get_fields()
            # _hydrate_m2o_values(val, related_fields)
            # Создаём экземпляр связанной модели из dict
            known_fields = set(related_fields.keys())
            safe_vals = {k: v for k, v in val.items() if k in known_fields}
            values[field_name] = related_model(**safe_vals)


class OnchangeRequest(BaseModel):
    """Схема запроса onchange."""

    model: str  # Имя модели (например "chat_connector")
    trigger_field: str  # Поле которое изменилось
    values: dict[str, Any]  # Текущие значения формы


@router_private.get("/onchange/{model}")
async def get_onchange_fields(req: Request, model: str):
    """
    Получить список полей с onchange обработчиками для модели.

    Фронтенд вызывает при загрузке формы чтобы знать
    за какими полями следить.

    Args:
        model: Имя модели (snake_case, например "chat_connector")

    Returns:
        {"fields": ["type", "category", ...]}
    """
    env: "Environment" = req.app.state.env

    # Получаем класс модели
    try:
        model_class = env.models._get_model(model)
    except AttributeError:
        # Модель не найдена - возвращаем пустой список вместо ошибки
        return {"fields": []}

    # Получаем список полей с onchange
    fields = model_class.get_onchange_fields()

    return {"fields": fields}


@router_private.post("/onchange")
async def execute_onchange(req: Request, body: OnchangeRequest):
    """
    Выполнить onchange обработчик при изменении поля.

    Фронтенд вызывает когда пользователь изменяет поле
    у которого есть onchange обработчик.

    Args:
        body: {
            "model": "chat_connector",
            "trigger_field": "type",
            "values": {"type": "telegram", "name": "Test", ...}
        }

    Returns:
        {
            "values": {"connector_url": "...", "smtp_port": 587, ...},
            "fields": {"smtp_host": {...}, ...}
        }
    """
    env: "Environment" = req.app.state.env

    # Получаем класс модели
    try:
        model_class = env.models._get_model(body.model)
    except AttributeError:
        raise FaraException(
            {
                "content": f"Model '{body.model}' not found",
                "status_code": HTTP_404_NOT_FOUND,
            }
        )

    # Проверяем есть ли обработчики для этого поля
    handlers = model_class._get_onchange_handlers(body.trigger_field)
    if not handlers:
        return {"values": {}, "fields": {}}

    # Фильтруем только известные поля модели
    model_fields = model_class.get_fields()
    filtered_values = {
        k: v for k, v in body.values.items() if k in model_fields
    }

    # Конвертация M2O: dict → экземпляр связанной модели (рекурсивно).
    # Фронт присылает M2O как dict {id, name, ...} или как число (id).
    # Конструктор DotModel просто делает setattr — не конвертирует.
    # Без конвертации обработчик не сможет сделать self.product_id.uom_id.
    _hydrate_m2o_values(filtered_values, model_fields)

    try:
        instance = model_class(**filtered_values)
    except Exception as e:
        raise FaraException(
            {
                "content": f"Invalid values: {str(e)}",
                "status_code": HTTP_400_BAD_REQUEST,
            }
        )

    # Выполняем onchange
    onchange_result = await instance.execute_onchange(body.trigger_field)

    # Собираем default values для новых полей
    # (которых нет в текущих values и нет в onchange result)
    defaults = {}
    for name, field in model_class.get_fields().items():
        if name not in body.values and name not in onchange_result:
            if field.default is not None:
                if callable(field.default):
                    try:
                        defaults[name] = field.default()
                    except:
                        pass
                else:
                    defaults[name] = field.default

    # Мержим: defaults < onchange_result (onchange имеет приоритет)
    result_values = {**defaults, **onchange_result}

    # Собираем информацию о полях
    fields_info = {}
    for name, field in model_class.get_fields().items():
        fields_info[name] = {
            "name": name,
            "type": field.__class__.__name__,
            "options": field.options or [],
            "required": field.required or False,
        }

    return {"values": result_values}
