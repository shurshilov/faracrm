# Copyright 2025 FARA CRM
# Report DOCX Designer — routes: field catalog and live preview

import base64
import binascii
from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.status import HTTP_400_BAD_REQUEST

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.report_docx.routers.reports import (
    error_response,
    file_response,
)
from backend.base.system.schemas.base_schema import Id
from ..catalog import template_field_catalog

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

router_private = APIRouter(
    tags=["Report DOCX Designer"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


class PreviewRequest(BaseModel):
    """Превью конструктора: несохранённый DOCX из редактора + параметры."""

    template_id: Id
    content: str  # DOCX в base64
    params: dict = {}
    output_format: Literal["docx", "pdf"] | None = None


@router_private.post("/reports/preview")
async def preview_report(req: Request, payload: PreviewRequest):
    """
    Рендер переданного DOCX (несохранённая правка из редактора) с данными по
    настройкам шаблона — тот же путь, что у ReportTemplate.render_attachment,
    но байты берутся из запроса. Файл в base64, как у загрузки вложений.
    """
    env: "Environment" = req.app.state.env
    try:
        template_bytes = base64.b64decode(payload.content, validate=True)
    except (binascii.Error, ValueError):
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"error": "content must be base64"},
        )

    templates = env.models.report_template
    try:
        tmpl = await templates.get_template(payload.template_id)
        report = await templates.render_bytes(
            tmpl, template_bytes, payload.params, payload.output_format
        )
    except Exception as e:
        return error_response(e)
    return file_response(report)


@router_private.get("/reports/templates/{template_id}/fields")
async def template_fields(req: Request, template_id: Id):
    """Каталог полей шаблона для конструктора — см. catalog.py."""
    try:
        data = await template_field_catalog(template_id)
    except Exception as e:
        return error_response(e)
    return {"data": data}
