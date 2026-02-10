# Copyright 2025 FARA CRM
# Chat module - WebSocket router

import logging
from typing import TYPE_CHECKING
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.base.crm.chat.websocket import chat_manager

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)

router_public = APIRouter(tags=["Chat WebSocket"])


@router_public.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint для real-time чата.

    Требует авторизации через query параметр token.
    """
    # Сначала принимаем соединение
    await websocket.accept()

    # Получаем токен из query параметров
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=4001, reason="Token required")
        return

    # Проверяем токен
    env: "Environment" = websocket.app.state.env

    try:
        sessions = await env.models.session.search(
            filter=[("token", "=", token), ("active", "=", True)],
            limit=1,
            fields=["id", "user_id"],
        )

        if not sessions:
            await websocket.close(code=4001, reason="Invalid token")
            return

        user_session = sessions[0]
        user_id = user_session.user_id.id

    except Exception as e:
        logger.error("WebSocket auth error: %s", e)
        await websocket.close(code=4001, reason="Auth error")
        return

    # Подключаем пользователя
    connected = await chat_manager.connect(websocket, user_id)

    if not connected:
        return

    try:
        while True:
            data = await websocket.receive_json()
            await chat_manager.handle_message(websocket, user_id, data)

    except WebSocketDisconnect:
        await chat_manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error("WebSocket error for user %s: %s", user_id, e)
        await chat_manager.disconnect(websocket, user_id)
