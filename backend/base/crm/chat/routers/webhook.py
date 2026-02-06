# Copyright 2025 FARA CRM
# Chat module - webhook router for external integrations
#
# Этот роутер содержит только HTTP слой.
# Вся бизнес-логика обработки сообщений находится в стратегиях (strategies/).

import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)

router_public = APIRouter(tags=["Chat Webhook"])


@router_public.api_route(
    "/chat/webhook/{webhook_hash}/{connector_id}",
    methods=["GET", "POST"],
)
async def chat_webhook(
    req: Request,
    webhook_hash: str,
    connector_id: int,
):
    """
    Универсальный webhook endpoint для приёма сообщений от внешних сервисов.

    Поддерживает:
    - Telegram
    - WhatsApp (ChatApp, Twilio и др.)
    - Avito
    - VK
    - и другие через стратегии

    Args:
        webhook_hash: Секретный хеш для валидации
        connector_id: ID коннектора

    Формат входящих данных зависит от провайдера и обрабатывается
    соответствующей стратегией через метод handle_webhook.
    """
    env: "Environment" = req.app.state.env

    # 1. Читаем сырые данные
    try:
        raw_data = await req.body()
        data = raw_data.decode("utf-8")

        if not data:
            logger.warning("Chat webhook: Empty data received")
            return PlainTextResponse("OK", status_code=HTTP_200_OK)

        payload = json.loads(data)
        logger.info(f"Chat webhook raw data: {payload}")

    except json.JSONDecodeError as e:
        logger.error(f"Chat webhook: Invalid JSON: {e}")
        return JSONResponse(
            content={"error": "INVALID_JSON"}, status_code=HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Chat webhook: Error reading data: {e}")
        return JSONResponse(
            content={"error": "READ_ERROR"}, status_code=HTTP_400_BAD_REQUEST
        )

    # 2. Получаем коннектор и валидируем
    connector = await env.models.chat_connector.get(connector_id)

    # 3. Проверяем webhook_hash
    if connector.webhook_hash != webhook_hash:
        logger.warning(
            f"Chat webhook: Invalid hash for connector {connector_id}"
        )
        return JSONResponse(
            content={"error": "INVALID_HASH"},
            status_code=HTTP_403_FORBIDDEN,
        )

    # 4. Проверяем активность коннектора
    if not connector.active:
        logger.warning(f"Chat webhook: Connector {connector_id} is inactive")
        return JSONResponse(
            content={"error": "CONNECTOR_INACTIVE"},
            status_code=HTTP_400_BAD_REQUEST,
        )

    # 5. Делегируем обработку стратегии (вне транзакции - стратегия сама управляет транзакциями)
    strategy = connector.strategy
    result = await strategy.handle_webhook(
        connector=connector,
        payload=payload,
        env=env,
    )

    return JSONResponse(content=result, status_code=HTTP_200_OK)
