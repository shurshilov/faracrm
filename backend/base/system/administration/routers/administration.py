from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from urllib.parse import quote
from starlette.exceptions import HTTPException
from fastapi.responses import Response

from backend.project_info import VERSION
from backend.base.system.core.enviroment import env
from backend.base.crm.auth_token.app import AuthTokenApp
from ..app import AdministrationApp

router_public = APIRouter(
    tags=[f"{AdministrationApp.info.get("name")}"],
    dependencies=[
        Depends(
            AuthTokenApp.use_anonymous_session(
                ["company", "system_settings", "attachments"]
            )
        )
    ],
)

router_private = APIRouter(
    tags=[f"{AdministrationApp.info.get("name")}"],
    dependencies=[Depends(env.apps.auth.verify_access)],
)


@router_private.get("/apps/", response_model=dict)
def apps():
    apps = {}
    for app in env.apps.get_list():
        apps |= {f"{app.info.get("name")}": app.info}
    return apps


@router_public.get("/version/", response_model=str)
def version():
    return VERSION


class BrandingConfig(BaseModel):
    """Настройки бренда. URL-ы фронт строит сам через
    `${API_BASE_URL}/api/public/branding/<field>`."""

    has_logo: bool = False
    has_login_logo: bool = False
    has_login_background: bool = False
    login_title: str | None = None
    login_subtitle: str | None = None
    login_button_color: str | None = None
    login_card_style: str = "elevated"


class PublicConfig(BaseModel):
    """Публичная конфигурация, доступная до логина."""

    version: str
    demo_mode: bool
    branding: BrandingConfig


async def _get_first_company():
    """Первая активная компания или None."""
    companies = await env.models.company.search(
        filter=[("active", "=", True)],
        order="asc",
        sort="sequence",
        limit=1,
        fields=[
            "id",
            "logo_id",
            "login_logo_id",
            "login_background_id",
            "login_title",
            "login_subtitle",
            "login_button_color",
            "login_card_style",
        ],
        fields_nested={
            "logo_id": ["id"],
            "login_logo_id": ["id"],
            "login_background_id": ["id"],
        },
    )
    return companies[0] if companies else None


@router_public.get("/public/config/", response_model=PublicConfig)
async def public_config():
    """Конфиг для фронта (страница логина и т.п.)."""
    demo = await env.models.system_settings.get_value(
        "ui.demo_mode", default=False
    )
    company = await _get_first_company()
    branding = (
        BrandingConfig()
        if company is None
        else BrandingConfig(
            has_logo=bool(company.logo_id),
            has_login_logo=bool(company.login_logo_id),
            has_login_background=bool(company.login_background_id),
            login_title=company.login_title or None,
            login_subtitle=company.login_subtitle or None,
            login_button_color=company.login_button_color or None,
            login_card_style=company.login_card_style or "elevated",
        )
    )
    return PublicConfig(
        version=VERSION, demo_mode=bool(demo), branding=branding
    )


@router_public.get("/public/branding/{field}")
async def branding_file(
    field: Literal["logo_id", "login_logo_id", "login_background_id"],
):
    """Публичная отдача файла из Company.<field>.

    Использует sudo() для доступа к Attachment по конкретному ID —
    AnonymousSession имеет READ только к whitelist'у, и хотя attachments
    в нём, для удобства идём через sudo (явный обход).
    """

    company = await _get_first_company()
    if company is None or not getattr(company, field, None):
        raise HTTPException(status_code=404)

    attachment_ref = getattr(company, field)
    attachment_id = attachment_ref.id

    attaches = await env.models.attachment.search(
        filter=[("id", "=", attachment_id)],
        limit=1,
        fields=[
            "id",
            "name",
            "mimetype",
            "storage_file_url",
            "storage_file_id",
            "storage_id",
            "content",
        ],
        fields_nested={"storage_id": ["id", "type", "google_credentials"]},
    )
    if not attaches:
        raise HTTPException(status_code=404)

    attach = attaches[0]
    return Response(
        headers={
            "Content-Disposition": (
                f"inline;filename={quote(attach.name, safe='')}"
            ),
            "Cache-Control": "public, max-age=300",
        },
        media_type=attach.mimetype,
        content=await attach.read_content(),
    )
