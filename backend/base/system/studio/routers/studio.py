"""
Поля студии из интерфейса (меню «⋮ → Поля модели…»).

GET    /studio/fields/{model}  — поля студии модели
POST   /studio/fields          — добавить поле: строка, колонка, схемы, роуты
PATCH  /studio/fields/{id}     — подпись и варианты; имя и тип не меняются
DELETE /studio/fields/{id}     — убрать поле с модели; колонка и данные остаются

Только администратору настроек. Остальные воркеры и крон узнают об
изменении по событию studio_changed (StudioApp.publish).
"""

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.core.exceptions.environment import FaraException
from ..models.studio_field import StudioField

if TYPE_CHECKING:
    from backend.base.crm.security.models.sessions import Session
    from backend.base.system.core.enviroment import Environment

router_private = APIRouter(
    prefix="/studio",
    tags=["Studio"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)

FIELDS = [
    "id",
    "model_name",
    "name",
    "label",
    "field_type",
    "options",
    "relation_model",
]


class StudioFieldCreate(BaseModel):
    model_name: str
    name: str
    label: str
    field_type: str
    # Пары [значение, подпись] — у выбора из списка.
    options: list[list[str]] | None = None
    # Таблица связанной модели — у ссылки на запись.
    relation_model: str | None = None


class StudioFieldUpdate(BaseModel):
    label: str | None = None
    options: list[list[str]] | None = None


def _as_dict(row: StudioField) -> dict:
    return {
        "id": row.id,
        "model_name": row.model_name,
        "name": row.name,
        "label": row.label,
        "field_type": row.field_type,
        "options": json.loads(row.options) if row.options else None,
        "relation_model": row.relation_model,
    }


@router_private.get("/fields/{model}")
async def list_fields(req: Request, model: str) -> list[dict]:
    auth_session: "Session" = req.state.session
    auth_session.check_system_admin()
    env: "Environment" = req.app.state.env
    rows = await env.models.studio_field.search(
        filter=[("model_name", "=", model)],
        fields=FIELDS,
        sort="id",
        order="asc",
    )
    return [_as_dict(row) for row in rows]


@router_private.post("/fields")
async def create_field(req: Request, payload: StudioFieldCreate) -> dict:
    auth_session: "Session" = req.state.session
    auth_session.check_system_admin()
    env: "Environment" = req.app.state.env
    studio = env.apps.studio

    # Строка (проверки — @constrains модели), поле на модель, колонка,
    # поле в «Дополнительно» формы, схемы и роуты этого воркера, событие
    # остальным.
    row_id = await env.models.studio_field.create(
        StudioField(
            model_name=payload.model_name,
            name=payload.name.strip(),
            label=payload.label.strip(),
            field_type=payload.field_type,
            options=(
                json.dumps(payload.options, ensure_ascii=False)
                if payload.options
                else None
            ),
            relation_model=payload.relation_model,
        )
    )
    added, _ = await studio.refresh()
    if added:
        await env.apps.db.sync_tables(added)
    await studio.show_on_form(payload.model_name, payload.name.strip())
    await studio.rebuild(req.app)
    await studio.publish()
    return {"id": row_id}


@router_private.patch("/fields/{field_id}")
async def update_field(
    req: Request, field_id: int, payload: StudioFieldUpdate
) -> dict:
    auth_session: "Session" = req.state.session
    auth_session.check_system_admin()
    env: "Environment" = req.app.state.env
    studio = env.apps.studio

    row = await env.models.studio_field.search_one(
        filter=[("id", "=", field_id)], fields=FIELDS
    )
    if not row:
        raise FaraException({"content": "#NOT_FOUND", "status_code": 404})

    values = StudioField()
    if payload.label is not None:
        if not payload.label.strip():
            raise FaraException(
                {"content": "STUDIO_FIELD_BAD_LABEL", "status_code": 400}
            )
        values.label = payload.label.strip()
    if payload.options is not None:
        values.options = json.dumps(payload.options, ensure_ascii=False)
    if not values.assigned_fields():
        return _as_dict(row)

    # Строка (варианты проверяет @constrains), поле на месте в этом
    # воркере (refresh), событие остальным; схемы не трогаем.
    await row.update(values)
    await studio.refresh()
    await studio.publish()
    return _as_dict(row)


@router_private.delete("/fields/{field_id}")
async def delete_field(req: Request, field_id: int) -> bool:
    auth_session: "Session" = req.state.session
    auth_session.check_system_admin()
    env: "Environment" = req.app.state.env
    studio = env.apps.studio

    row = await env.models.studio_field.search_one(
        filter=[("id", "=", field_id)], fields=FIELDS
    )
    if not row:
        raise FaraException({"content": "#NOT_FOUND", "status_code": 404})

    # Строка, поле с модели, упоминания в настройках формы, схемы и роуты
    # этого воркера, событие остальным. Колонку с данными НЕ трогаем:
    # поле с тем же именем и типом, созданное заново, получит прежние
    # значения (ADD COLUMN IF NOT EXISTS). Удаление колонки отключено
    # намеренно — чтобы вернуть, раскомментировать строку ниже и
    # drop_column в сервисе базы.
    await row.delete()
    await studio.refresh()
    # await env.apps.db.drop_column(row.model_name, row.name)
    await studio.forget(row.model_name, row.name)
    await studio.rebuild(req.app)
    await studio.publish()
    return True
