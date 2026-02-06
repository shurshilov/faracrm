# Copyright 2025 FARA CRM
# Report DOCX module — report generation router

import logging
from typing import TYPE_CHECKING
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import Response, JSONResponse
from starlette.status import HTTP_404_NOT_FOUND, HTTP_400_BAD_REQUEST

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


@router_private.get("/reports/generate/{template_id}/{record_id}")
async def generate_report(
    req: Request,
    template_id: Id,
    record_id: Id,
    output_format: str | None = Query(
        None,
        description="Override: 'docx' or 'pdf'. Default from template.",
    ),
):
    """
    Генерация отчёта из DOCX-шаблона.

    1. template_id → report_template (model_name, python_function, template_file)
    2. getattr(model_cls, python_function)(env, record_id) → context dict
    3. docxtpl.render(context)
    4. Опционально LibreOffice → PDF
    """
    env: "Environment" = req.app.state.env

    # 1. Шаблон
    templates = await env.models.report_template.search(
        filter=[("id", "=", template_id)],
        limit=1,
        fields=[
            "id",
            "name",
            "model_name",
            "python_function",
            "template_file",
            "output_format",
        ],
        # fields_nested={
        #     "template_file": [
        #         "id",
        #         "name",
        #         "storage_file_url",
        #         "storage_file_id",
        #         "mimetype",
        #         "storage_id",
        #     ],
        # },
    )
    if not templates:
        return JSONResponse(
            status_code=HTTP_404_NOT_FOUND,
            content={"error": f"Template #{template_id} not found"},
        )

    tmpl = templates[0]
    attachment = tmpl.template_file
    if attachment is None:
        return JSONResponse(
            status_code=HTTP_404_NOT_FOUND,
            content={"error": f"Template #{template_id} Attachment not found"},
        )
    attachment = await env.models.attachment.search(
        filter=[("id", "=", attachment.id)],
        # fields=["id", "storage_id", "storage_file_url"]
    )
    attachment = attachment[0]
    model_name = tmpl.model_name or ""
    func_name = tmpl.python_function or ""
    fmt = output_format or tmpl.output_format or "docx"
    report_name = tmpl.name or "report"

    if not attachment:
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"error": "Template has no DOCX file attached"},
        )

    # 2. Модель и функция подготовки данных
    model_cls = getattr(env.models, model_name, None)
    if model_cls is None:
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"error": f"Model '{model_name}' not found"},
        )

    report_func = getattr(model_cls, func_name, None)
    if report_func is None:
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={
                "error": f"Function '{func_name}' not found on model '{model_name}'"
            },
        )

    # 3. Данные
    try:
        context = await report_func(env, record_id)
    except (ValueError, RecordNotFound) as e:
        return JSONResponse(
            status_code=HTTP_404_NOT_FOUND,
            content={"error": str(e)},
        )
    except Exception as e:
        log.exception(f"Data preparation error: {e}")
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"error": f"Data error: {e}"},
        )

    # 4. Рендер
    try:
        template_bytes = await attachment.read_content()
        if not template_bytes:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"error": "Could not read template file from storage"},
            )

        file_bytes, content_type = DocxReportEngine.generate(
            template_bytes=template_bytes,
            context=context,
            output_format=fmt,
        )
    except RuntimeError as e:
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"error": str(e)},
        )
    except Exception as e:
        log.exception(f"Render error: {e}")
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"error": f"Render error: {e}"},
        )

    # 5. Отдаём файл
    ext = "pdf" if fmt == "pdf" else "docx"
    filename = f"{report_name}_{record_id}.{ext}"
    filename_enc = quote(filename, safe="")

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename_enc}"'
                # f"filename*=UTF-8''{quote(filename_enc, safe="")}"
            ),
        },
    )
