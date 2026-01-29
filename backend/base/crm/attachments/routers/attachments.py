import aiofiles
import os
import io
from typing import TYPE_CHECKING, Optional
from fastapi import APIRouter, Depends, Request, Response, Query
from fastapi.responses import JSONResponse
from starlette.status import HTTP_404_NOT_FOUND
from PIL import Image

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
    # async with aiofiles.open(
    #     f"{attach.storage_file_url}",
    #     "rb",
    # ) as file:
    #     attachment_content = await file.read()

    return Response(
        headers={
            "Content-Disposition": f"Attachment" f""";filename={attach.name}"""
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
    # if not attach.storage_file_url or not os.path.exists(
    #     attach.storage_file_url
    # ):
    #     return JSONResponse(
    #         content={"error": "#FILE_NOT_FOUND"},
    #         status_code=HTTP_404_NOT_FOUND,
    #     )

    # async with aiofiles.open(
    #     f"{attach.storage_file_url}",
    #     "rb",
    # ) as file:
    #     attachment_content = await file.read()

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

    return Response(
        headers={"Content-Disposition": f"inline; filename={attach.name}"},
        media_type=attach.mimetype,
        content=attachment_content,
    )


# @router_public.get("/sw.js")
# async def service_worker(req: Request):
#     code = """
#         self.addEventListener('fetch', function(event) {
#             const session = JSON.parse(localStorage.getItem('session') || '{}')
#             const newRequest = new Request(event.request, {
#                 headers: {"Authorization": session.token},
#                 mode: "cors"
#             });
#             return fetch(newRequest);
#         }
#     """
#     return PlainTextResponse(
#         # headers={"Content-Disposition": f"Attachment" f""";filename=sw.js"""},
#         media_type="text/javascript",
#         content=code,
#     )
