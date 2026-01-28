# Copyright 2025 FARA CRM
# Chat module - connectors router (специфичные endpoints)
#
# CRUD операции (create, read, update, delete) обрабатываются автоматически
# через dotorm_crud_auto. Этот роутер содержит только специфичную логику:
# - webhook управление (set/unset/info)
# - типы коннекторов
#
# Webhook callback endpoint находится в webhook.py

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from starlette.status import HTTP_404_NOT_FOUND

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.core.exceptions.environment import FaraException

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment


router_private = APIRouter(
    tags=["Chat Connectors"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


# ============================================================================
# Webhook управление
# ============================================================================


@router_private.post("/connectors/{connector_id}/webhook/set")
async def set_connector_webhook(req: Request, connector_id: int):
    """
    Установить webhook для коннектора.

    Отправляет запрос к внешнему API (например, Telegram)
    для регистрации webhook URL.
    """
    env: "Environment" = req.app.state.env

    try:
        connector = await env.models.chat_connector.get(connector_id)
    except ValueError:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    # Передаём base_url из request если нет в настройках
    base_url = str(req.base_url).rstrip("/")
    success = await connector.set_webhook(base_url=base_url)

    return {
        "success": success,
        "webhook_state": connector.webhook_state,
        "webhook_url": connector.webhook_url,
    }


@router_private.post("/connectors/{connector_id}/webhook/unset")
async def unset_connector_webhook(req: Request, connector_id: int):
    """
    Удалить webhook коннектора.

    Отправляет запрос к внешнему API для удаления webhook.
    """
    env: "Environment" = req.app.state.env

    try:
        connector = await env.models.chat_connector.get(connector_id)
    except ValueError:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    success = await connector.unset_webhook()

    return {"success": success, "webhook_state": connector.webhook_state}


@router_private.get("/connectors/{connector_id}/webhook/info")
async def get_connector_webhook_info(req: Request, connector_id: int):
    """
    Получить информацию о webhook от внешнего API.

    Возвращает текущее состояние webhook по данным провайдера.
    """
    env: "Environment" = req.app.state.env

    try:
        connector = await env.models.chat_connector.get(connector_id)
    except ValueError:
        raise FaraException(
            {"content": "NOT_FOUND", "status_code": HTTP_404_NOT_FOUND}
        )

    info = await connector.strategy.get_webhook_info(connector)

    return {"data": info}


# ============================================================================
# Типы коннекторов
# ============================================================================


# @router_private.get("/connectors/types")
# async def get_connector_types(req: Request):
#     """
#     Получить список доступных типов коннекторов.

#     Возвращает типы зарегистрированных стратегий.
#     """
#     from backend.base.crm.chat.strategies import list_strategies

#     return {"types": list_strategies()}
