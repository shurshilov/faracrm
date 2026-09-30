# Copyright 2025 FARA CRM
# Report DOCX module — report generation router

import asyncio
import json
import logging
from typing import TYPE_CHECKING
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import Response, JSONResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.schemas.base_schema import Id
from backend.base.system.dotorm.dotorm.exceptions import RecordNotFound
from ..utils.engine import DocxReportEngine

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

log = logging.getLogger(__name__)

router_private = APIRouter(
    tags=["Report DOCX"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


def file_response(report) -> Response:
    """Готовый отчёт (несохранённый Attachment) как скачиваемый файл."""
    filename_enc = quote(report.name, safe="")
    return Response(
        content=report.content,
        media_type=report.mimetype,
        # Без filename* браузер не переведет проценты обратно в буквы
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{filename_enc}",
        },
    )


def error_response(error: Exception) -> JSONResponse:
    """Ошибки сборки → JSON: 404 нет шаблона/записи, 400 остальное."""
    if isinstance(error, RecordNotFound):
        return JSONResponse(
            status_code=HTTP_404_NOT_FOUND, content={"error": str(error)}
        )
    if isinstance(error, (ValueError, RuntimeError, TypeError)):
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST, content={"error": str(error)}
        )
    log.exception("Report generation error: %s", error)
    return JSONResponse(
        status_code=HTTP_400_BAD_REQUEST,
        content={"error": f"Report error: {error}"},
    )


@router_private.get("/reports/generate/{template_id}")
@router_private.get("/reports/generate/{template_id}/{record_id}")
async def generate_report(
    req: Request,
    template_id: Id,
    record_id: Id | None = None,
    output_format: str | None = Query(
        None,
        description="Override: 'docx' or 'pdf'. Default from template.",
    ),
    params: str | None = Query(
        None,
        description='JSON-параметры функции данных, напр. {"days": 30}',
    ),
):
    """
    Генерация отчёта из DOCX-шаблона — см. ReportTemplate.render_attachment
    (тот же путь используют cron-рассылки).

    С record_id — документ по записи (кнопка «Печать»), без него — сводный
    отчёт: параметры функции данных передаются в ?params= (JSON-объект).
    """
    env: "Environment" = req.app.state.env

    try:
        call_params = json.loads(params) if params else {}
        if not isinstance(call_params, dict):
            raise ValueError("params must be a JSON object")
    except ValueError as e:
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"error": f"Bad params: {e}"},
        )
    if record_id is not None:
        call_params["record_id"] = record_id

    try:
        report = await env.models.report_template.render_attachment(
            template_id, call_params, output_format
        )
    except Exception as e:
        return error_response(e)
    return file_response(report)


@router_private.get("/reports/pdf-engine")
async def pdf_engine(
    req: Request,
    recheck: bool = Query(
        False,
        description="Заново поискать LibreOffice (поставили без рестарта)",
    ),
):
    """
    Каким движком собираются PDF — индикатор в тулбаре списка шаблонов:
    {"engine": "libreoffice"|"builtin", "path", "version"}.

    Только администратору (как и правка шаблонов): путь к бинарнику и версия
    — детали сервера, рядовому пользователю они ничего не объясняют.
    """
    user = req.state.session.user_id
    if not (
        user.is_admin
        or any(role.code == "system_admin" for role in (user.role_ids or []))
    ):
        raise HTTPException(HTTP_403_FORBIDDEN, "ADMIN_REQUIRED")
    # Поиск запускает процесс `soffice --version` — не в event loop
    info = await asyncio.to_thread(DocxReportEngine.pdf_engine_info, recheck)
    return {"data": info}
