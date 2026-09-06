# Copyright (c) 2024-2026 FARA CRM Authors
# Licensed under the FARA CRM License v1.0

"""
Установка и удаление приложений из интерфейса.

GET  /apps/catalog            — все приложения реестра с флагом installed
POST /apps/{code}/install     — установить вместе с зависимостями
POST /apps/{code}/uninstall   — удалить вместе с зависимыми

Логика — Environment.install_apps / uninstall_apps; здесь права (is_admin
или роль system_admin) и форма ответа. Каталог собирается из info модулей
в памяти: в БД у приложения только флаг installed.
"""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.core.exceptions.environment import FaraException

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from ..models.sessions import Session

router_private = APIRouter(
    prefix="/apps",
    tags=["Apps"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


def _require_manager(session: "Session") -> None:
    """Ставить и удалять приложения может суперпользователь или
    администратор настроек (роль system_admin)."""
    user = session.user_id
    if user.is_admin or any(
        role.code == "system_admin" for role in (user.role_ids or [])
    ):
        return
    raise FaraException(
        {
            "content": "#ACCESS_DENIED",
            "detail": "system_admin",
            "status_code": 403,
        }
    )


@router_private.get("/catalog")
async def apps_catalog(req: Request) -> dict:
    """Контракт с фронтом:
    apps     — реестр в порядке sequence: код, имя, описание, зависимости,
               core, installed, app_key (= ui_menu_name UI-приложения);
    app_keys — ключи групп меню установленных UI-приложений.
    """
    env: "Environment" = req.app.state.env
    apps = env.apps

    catalog = []
    for code in apps.get_names():
        info = apps.get(code).info or {}
        catalog.append(
            {
                "code": code,
                "name": info.get("name", code),
                "summary": " ".join((info.get("summary") or "").split()),
                "category": info.get("category"),
                "version": info.get("version"),
                "depends": apps.depends_of(code),
                "core": apps.is_core(code),
                "installed": code in env.installed,
                "app_key": (
                    info.get("ui_menu_name") if info.get("ui_menu") else None
                ),
            }
        )
    app_keys = sorted(
        {a["app_key"] for a in catalog if a["installed"] and a["app_key"]}
    )
    return {"apps": catalog, "app_keys": app_keys}


@router_private.post("/{code}/install")
async def install_app(req: Request, code: str) -> dict:
    """Установить приложение и его недостающие зависимости.
    Возвращает, что было установлено (в порядке установки)."""
    _require_manager(req.state.session)
    env: "Environment" = req.app.state.env
    return {"installed": await env.install_apps([code], req.app)}


@router_private.post("/{code}/uninstall")
async def uninstall_app(req: Request, code: str) -> dict:
    """Удалить приложение и установленные зависимые от него.
    Возвращает, что было удалено (зависимые — первыми)."""
    _require_manager(req.state.session)
    env: "Environment" = req.app.state.env
    return {"uninstalled": await env.uninstall_apps([code], req.app)}
