from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.project_info import VERSION
from backend.base.system.core.enviroment import env
from ..app import AdministrationApp

router_public = APIRouter(
    tags=[f"{AdministrationApp.info.get("name")}"],
)

router_private = APIRouter(
    tags=[f"{AdministrationApp.info.get("name")}"],
    dependencies=[Depends(env.apps.auth.verify_access)],
)


@router_private.get("/api/apps/", response_model=dict)
def apps():
    apps = {}
    for app in env.apps.get_list():
        apps |= {f"{app.info.get("name")}": app.info}
    return apps


@router_public.get("/api/version/", response_model=str)
def version():
    return VERSION


class PublicConfig(BaseModel):
    """
    Публичная конфигурация, доступная до логина.
    Содержит только те флаги, которые безопасно светить анонимно.
    """

    version: str
    demo_mode: bool


@router_public.get("/api/public/config/", response_model=PublicConfig)
async def public_config():
    """Конфиг для фронта (страница логина и т.п.)."""

    demo = await env.models.system_settings.get_value(
        "ui.demo_mode",
        default=False,
    )
    return PublicConfig(version=VERSION, demo_mode=bool(demo))
