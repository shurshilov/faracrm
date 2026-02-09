# Copyright (c) 2024-2026 FARA CRM Authors
# Licensed under the FARA CRM License v1.0

"""
Роутер для статических файлов приложений (иконки).

Отдаёт иконки модулей по пути /static/app-icons/{app_code}.svg
Если иконка не найдена — возвращает 404 (фронт покажет fallback).
"""

import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

router_public = APIRouter(prefix="/static/app-icons", tags=["static"])

# Словарь путей к иконкам приложений (заполняется при старте)
_app_icons: dict[str, str] = {}


def register_app_icon(app_code: str, icon_path: str):
    """Регистрирует путь к иконке приложения."""
    if os.path.exists(icon_path):
        _app_icons[app_code] = icon_path


def get_registered_icons() -> list[str]:
    """Возвращает список зарегистрированных иконок."""
    return list(_app_icons.keys())


@router_public.get("/{app_code}.svg")
async def get_app_icon(app_code: str) -> Response:
    """
    Получить иконку приложения.

    Возвращает SVG иконку для указанного приложения.
    Если иконка не найдена — возвращает 404 (фронт покажет fallback).
    """
    icon_path = _app_icons.get(app_code)

    if icon_path and os.path.exists(icon_path):
        return FileResponse(
            icon_path,
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    raise HTTPException(status_code=404, detail="Icon not found")


@router_public.get("/")
async def list_app_icons() -> dict:
    """
    Список всех зарегистрированных иконок приложений.
    """
    return {
        "icons": list(_app_icons.keys()),
    }
