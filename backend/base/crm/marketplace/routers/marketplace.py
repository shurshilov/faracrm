# Copyright 2025 FARA CRM
# Marketplace module - публичный каталог, покупка, скачивание, статистика

import logging
from typing import TYPE_CHECKING
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response
from starlette.status import HTTP_404_NOT_FOUND

from backend.base.crm.attachments.routers.attachments import (
    RESIZABLE_MIMETYPES,
    resize_image,
)
from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.marketplace.models.marketplace_app import (
    ATTACHMENT_CONTENT_FIELDS,
    IMAGE_MIMETYPE_PATTERN,
    MarketplaceApplication,
)
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.fields import Decimal
from backend.base.system.schemas.base_schema import Id

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)

# Каталог без входа. Анонимной сессии разрешено только чтение этих таблиц,
# правила доступа к ней не применяются — поэтому published фильтруем сами.
router_public = APIRouter(
    tags=["Marketplace"],
    dependencies=[
        Depends(
            AuthTokenApp.use_anonymous_session(
                [
                    "marketplace_app",
                    "users",
                    "attachments",
                    "attachment_storage",
                ]
            )
        )
    ],
)
router_private = APIRouter(
    tags=["Marketplace"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)
# Скачивание идёт по ссылке <a href>, поэтому авторизация кукой (как у
# контента вложений).
router_content = APIRouter(
    tags=["Marketplace"],
    dependencies=[Depends(AuthTokenApp.verify_access_by_cookie)],
)

APP_FIELDS = [
    "id",
    "name",
    "summary",
    "category",
    "version",
    "price",
    "downloads",
    "verified",
    "create_user_id",
]
VENDOR_NESTED = {"create_user_id": ["id", "name", "verified"]}
SORTS = {
    "popular": ("downloads", "desc"),
    "new": ("id", "desc"),
    "price": ("price", "asc"),
}


def _not_found() -> FaraException:
    return FaraException(
        {"content": "#NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
    )


def _serialize(app: MarketplaceApplication, cover_id: int | None) -> dict:
    vendor = app.create_user_id
    return {
        "id": app.id,
        "name": app.name,
        "summary": app.summary,
        "category": app.category,
        "version": app.version,
        "price": float(Decimal.to_decimal(app.price)),
        "downloads": app.downloads or 0,
        "verified": bool(app.verified),
        "vendor": (
            {
                "id": vendor.id,
                "name": vendor.name,
                "verified": bool(vendor.verified),
            }
            if vendor
            else None
        ),
        "cover_id": cover_id,
    }


async def _published(
    env: "Environment", app_id: int, fields: list[str]
) -> MarketplaceApplication:
    rows = await env.models.marketplace_app.search(
        fields=fields,
        fields_nested=VENDOR_NESTED,
        filter=[("id", "=", app_id), ("published", "=", True)],
        limit=1,
    )
    if not rows:
        raise _not_found()
    return rows[0]


@router_public.get("/marketplace/apps")
async def list_apps(
    req: Request,
    search: str = "",
    category: str = "",
    free: bool | None = None,
    sort: str = "popular",
    limit: int = Query(24, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Опубликованные приложения: поиск по названию/описанию + фильтры.

    Пагинация: limit — размер страницы, offset — сдвиг; total — общее число
    подходящих записей (для пейджера на фронте).
    """
    env: "Environment" = req.app.state.env

    filter_: list = [("published", "=", True)]
    if category:
        filter_.append(("category", "=", category))
    if free is True:
        filter_.append(("price", "=", 0))
    elif free is False:
        filter_.append(("price", ">", 0))
    if search.strip():
        pattern = f"%{search.strip()}%"
        filter_.append(
            [("name", "ilike", pattern), "or", ("summary", "ilike", pattern)]
        )
    sort_field, order = SORTS.get(sort, SORTS["popular"])

    total = await env.models.marketplace_app.search_count(filter=filter_)
    apps = await env.models.marketplace_app.search(
        fields=APP_FIELDS,
        fields_nested=VENDOR_NESTED,
        filter=filter_,
        sort=sort_field,
        order=order,
        start=offset,
        limit=limit,
    )
    covers: dict[int, int] = {}
    screenshots = await env.models.marketplace_app.get_screenshots(
        [app.id for app in apps]
    )
    for shot in screenshots:
        covers.setdefault(shot.res_id, shot.id)
    return {
        "data": [_serialize(app, covers.get(app.id)) for app in apps],
        "total": total,
    }


@router_public.get("/marketplace/apps/{app_id}")
async def get_app(req: Request, app_id: Id):
    env: "Environment" = req.app.state.env
    app = await _published(env, app_id, APP_FIELDS + ["description"])
    screenshots = await env.models.marketplace_app.get_screenshots([app.id])
    data = _serialize(app, screenshots[0].id if screenshots else None)
    data["description"] = app.description
    data["screenshots"] = [{"id": s.id, "name": s.name} for s in screenshots]
    # Архив из git-хранилища — ссылка на исходники. У файлового хранилища
    # storage_file_url — путь на диске, его наружу не отдаём.
    archive = await app.get_archive()
    data["source_url"] = (
        archive.storage_file_url
        if archive and getattr(archive.storage_id, "type", None) == "git"
        else None
    )
    return {"data": data}


@router_public.get("/marketplace/apps/{app_id}/image/{attachment_id}")
async def app_image(
    req: Request,
    app_id: Id,
    attachment_id: Id,
    w: int | None = Query(None, ge=1, le=2000),
    h: int | None = Query(None, ge=1, le=2000),
):
    """Скриншот опубликованного приложения (без входа, с ресайзом)."""
    env: "Environment" = req.app.state.env
    await _published(env, app_id, ["id"])

    rows = await env.models.attachment.search(
        fields=ATTACHMENT_CONTENT_FIELDS,
        filter=[
            ("id", "=", attachment_id),
            ("res_model", "=", MarketplaceApplication.__table__),
            ("res_id", "=", app_id),
            ("mimetype", "like", IMAGE_MIMETYPE_PATTERN),
        ],
        limit=1,
    )
    if not rows:
        raise _not_found()
    attachment = rows[0]
    content = await attachment.read_content()
    if content is None:
        raise _not_found()

    if (w or h) and attachment.mimetype in RESIZABLE_MIMETYPES:
        try:
            content = resize_image(
                content, w or h or 100, h or w or 100, attachment.mimetype
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Resize image fails, return the original: %s", e)

    return Response(
        content=content,
        media_type=attachment.mimetype,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router_public.get("/marketplace/apps/{app_id}/download-free")
async def download_free(req: Request, app_id: Id):
    """Скачать бесплатный модуль — без входа (платный сюда не отдаём).

    Логин требуется только за платными: их архив за деньги, отдаёт
    авторизованная ручка download ниже.
    """
    env: "Environment" = req.app.state.env
    rows = await env.models.marketplace_app.search(
        fields=["id", "name", "price"],
        filter=[("id", "=", app_id), ("published", "=", True)],
        limit=1,
    )
    if not rows:
        raise _not_found()
    app = rows[0]
    if Decimal.to_decimal(app.price) > 0:
        raise _not_found()

    archive = await app.get_archive()
    content = await archive.read_content() if archive else None
    if content is None:
        raise _not_found()

    # Счётчик скачиваний — прямым SQL (правила дают править запись только
    # поставщику; здесь качает аноним). Как в авторизованной download ниже.
    await env.apps.db.get_session().execute(
        "UPDATE marketplace_app SET downloads = downloads + 1 WHERE id = %s",
        [app.id],
        cursor="void",
    )
    return Response(
        content=content,
        media_type=archive.mimetype or "application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=utf-8''{quote(archive.name, safe='')}"
            )
        },
    )


@router_private.post("/marketplace/apps/{app_id}/buy")
async def buy_app(req: Request, app_id: Id):
    """Купить (или получить бесплатно). Для платных — ссылка на оплату."""
    env: "Environment" = req.app.state.env
    user_id = req.state.session.user_id.id

    async with env.apps.db.get_transaction():
        purchase = await env.models.marketplace_purchase.buy(app_id, user_id)

    payment = purchase.payment_id
    return {
        "data": {
            "purchase_id": purchase.id,
            "state": purchase.state,
            "payment_url": (
                payment.payment_url
                if payment and purchase.state != "paid"
                else None
            ),
        }
    }


@router_private.post("/marketplace/git-sync")
async def git_sync(req: Request):
    """Импорт модулей репозитория в каталог (суперпользователь). Записи не
    опубликованы — админ проверяет карточки и публикует сам."""
    env: "Environment" = req.app.state.env
    if not req.state.session.user_id.is_admin:
        raise FaraException(
            {
                "content": "MARKETPLACE_ADMIN_ONLY",
                "detail": "Только для администратора",
                "status_code": 403,
            }
        )
    async with env.apps.db.get_transaction():
        created = await env.models.marketplace_app.sync_from_git()
    return {"data": {"created": created}}


@router_private.get("/marketplace/my/stats")
async def my_stats(req: Request):
    """Статистика поставщика по его приложениям."""
    env: "Environment" = req.app.state.env
    user_id = req.state.session.user_id.id

    rows = await env.apps.db.get_session().execute(
        """
        SELECT a.id, a.name, a.price, a.published, a.downloads,
               COUNT(p.id) FILTER (WHERE p.state = 'paid') AS purchases,
               COALESCE(SUM(p.amount) FILTER (WHERE p.state = 'paid'), 0)
                   AS revenue
        FROM marketplace_app a
        LEFT JOIN marketplace_purchase p ON p.app_id = a.id
        WHERE a.create_user_id = %s
        GROUP BY a.id
        ORDER BY a.id
        """,
        [user_id],
    )
    return {
        "data": [
            {
                "id": row["id"],
                "name": row["name"],
                "price": float(row["price"] or 0),
                "published": row["published"],
                "downloads": row["downloads"] or 0,
                "purchases": int(row["purchases"] or 0),
                "revenue": float(row["revenue"] or 0),
            }
            for row in rows
        ]
    }


@router_content.get("/marketplace/apps/{app_id}/download")
async def download_app(req: Request, app_id: Id):
    """Архив модуля: поставщику, покупателю и всем — если бесплатно."""
    env: "Environment" = req.app.state.env
    user = req.state.session.user_id

    app = await env.models.marketplace_app.get(
        app_id, fields=["id", "name", "price", "create_user_id"]
    )
    is_vendor = bool(app.create_user_id and app.create_user_id.id == user.id)
    if not is_vendor and Decimal.to_decimal(app.price) > 0:
        paid = await env.models.marketplace_purchase.search(
            fields=["id"],
            filter=[
                ("app_id", "=", app_id),
                ("user_id", "=", user.id),
                ("state", "=", "paid"),
            ],
            limit=1,
        )
        if not paid:
            raise FaraException(
                {
                    "content": "MARKETPLACE_NOT_PURCHASED",
                    "detail": "Приложение не куплено",
                    "status_code": 403,
                }
            )

    # Архив из git-хранилища сервер собирает прямо здесь (read_content).
    archive = await app.get_archive()
    content = await archive.read_content() if archive else None
    if content is None:
        raise _not_found()

    # Счётчик растёт от чужих скачиваний, а править запись могут только
    # поставщик и админ — поэтому прямым SQL, минуя правила.
    await env.apps.db.get_session().execute(
        "UPDATE marketplace_app SET downloads = downloads + 1 WHERE id = %s",
        [app.id],
        cursor="void",
    )
    return Response(
        content=content,
        media_type=archive.mimetype or "application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=utf-8''{quote(archive.name, safe='')}"
            )
        },
    )
