from fastapi import APIRouter, Depends

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
