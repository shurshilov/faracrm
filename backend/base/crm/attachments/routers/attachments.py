import io
from typing import TYPE_CHECKING, Optional
from fastapi import APIRouter, Depends, Request, Response, Query
from fastapi.responses import JSONResponse
from starlette.status import HTTP_404_NOT_FOUND
from PIL import Image
from urllib.parse import quote

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.schemas.base_schema import Id

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

router_public = APIRouter(
    tags=["Attachment"],
)
router_private = APIRouter(
    tags=["Attachment"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)
# Роутер для бинарного контента — поддержка авторизации через cookie
# Позволяет использовать <img src="...">, <a href="...">, <audio src="...">
# без необходимости передавать Authorization header
router_content = APIRouter(
    tags=["Attachment"],
    dependencies=[Depends(AuthTokenApp.verify_access_by_cookie)],
)

# Типы изображений, которые можно ресайзить
RESIZABLE_MIMETYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
}


def resize_image(
    image_bytes: bytes, width: int, height: int, mimetype: str
) -> bytes:
    """Ресайз изображения с сохранением пропорций"""
    img = Image.open(io.BytesIO(image_bytes))

    # Конвертируем RGBA в RGB для JPEG
    if img.mode == "RGBA" and mimetype in ("image/jpeg", "image/jpg"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background

    # Ресайз с сохранением пропорций (thumbnail)
    img.thumbnail((width, height), Image.Resampling.LANCZOS)

    # Сохраняем в буфер
    output = io.BytesIO()

    if mimetype == "image/png":
        img.save(output, format="PNG", optimize=True)
    elif mimetype == "image/gif":
        img.save(output, format="GIF")
    elif mimetype == "image/webp":
        img.save(output, format="WEBP", quality=85)
    else:
        img.save(output, format="JPEG", quality=85)

    return output.getvalue()


@router_private.get("/attachments/{attachment_id}")
async def attachment_content(req: Request, attachment_id: Id):
    """Скачать файл"""
    env: Environment = req.app.state.env
    attach = await env.models.attachment.search(
        filter=[("id", "=", attachment_id)],
        limit=1,
        fields=[
            "id",
            "model",
            "res_id",
            "name",
            "storage_file_url",
            "storage_file_id",
            "mimetype",
            "storage_id",
            "content",
        ],
        fields_nested={"storage_id": ["id", "type", "google_credentials"]},
    )
    if not attach:
        return JSONResponse(
            content={"error": "#NOT_FOUND"}, status_code=HTTP_404_NOT_FOUND
        )

    attach = attach[0]
    attachment_content = await attach.read_content()

    return Response(
        headers={
            "Content-Disposition": f"Attachment"
            f""";filename={quote(attach.name, safe="")}"""
        },
        media_type=attach.mimetype,
        content=attachment_content,
    )


@router_private.get("/attachments/{attachment_id}/preview")
async def attachment_preview(
    req: Request,
    attachment_id: Id,
    w: Optional[int] = Query(None, ge=1, le=2000, description="Width"),
    h: Optional[int] = Query(None, ge=1, le=2000, description="Height"),
):
    """Получить превью файла (для изображений) - inline отображение

    Параметры:
    - w: ширина (опционально)
    - h: высота (опционально)

    Если указаны w и/или h, изображение будет уменьшено с сохранением пропорций.
    """
    env: Environment = req.app.state.env
    attach = await env.models.attachment.search(
        filter=[("id", "=", attachment_id)],
        limit=1,
        fields=[
            "id",
            "model",
            "res_id",
            "name",
            "checksum",
            "storage_file_url",
            "storage_file_id",
            "mimetype",
            "storage_id",
            "content",
        ],
        fields_nested={"storage_id": ["id", "type", "google_credentials"]},
    )
    if not attach:
        return JSONResponse(
            content={"error": "#NOT_FOUND"}, status_code=HTTP_404_NOT_FOUND
        )

    attach = attach[0]
    attachment_content = await attach.read_content()

    # Ресайз если указаны размеры и это изображение
    if (w or h) and attach.mimetype in RESIZABLE_MIMETYPES:
        try:
            width = w or h or 100
            height = h or w or 100
            attachment_content = resize_image(
                attachment_content, width, height, attach.mimetype
            )
        except Exception:
            # Если ресайз не удался, возвращаем оригинал
            pass

    # ETag на основе checksum + размеров (уникальный ключ варианта)
    etag = f'"{attach.checksum or attach.id}-{w or 0}-{h or 0}"'

    # Если клиент прислал If-None-Match и checksum совпадает — 304
    if_none_match = req.headers.get("if-none-match")
    if if_none_match and if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})

    return Response(
        headers={
            "Content-Disposition": f"inline; filename={quote(attach.name, safe='')}",
            "Cache-Control": "private, max-age=86400, immutable",
            "ETag": etag,
        },
        media_type=attach.mimetype,
        content=attachment_content,
    )


# ── Cookie-based routes for binary content ──────────────
# Дублируют /attachments/{id} и /attachments/{id}/preview
# но авторизуются через HttpOnly cookie (cookie_token).
# Фронт может использовать <img src="/api/content/attachments/123/preview">
# без Authorization header — cookie отправится автоматически.


@router_content.get("/attachments/{attachment_id}/content")
async def attachment_content_cookie(req: Request, attachment_id: Id):
    """Скачать файл (авторизация через cookie)"""
    return await attachment_content(req, attachment_id)


@router_content.get("/attachments/{attachment_id}/content/preview")
async def attachment_preview_cookie(
    req: Request,
    attachment_id: Id,
    w: Optional[int] = Query(None, ge=1, le=2000, description="Width"),
    h: Optional[int] = Query(None, ge=1, le=2000, description="Height"),
):
    """Превью файла (авторизация через cookie)"""
    return await attachment_preview(req, attachment_id, w, h)
