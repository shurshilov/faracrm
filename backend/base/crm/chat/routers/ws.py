# Copyright 2025 FARA CRM
# Chat module - WebSocket router

import logging
from typing import TYPE_CHECKING
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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
    # 1. Сначала извлекаем токен
    token = websocket.query_params.get("token")
    env: "Environment" = websocket.app.state.env

    if not token:
        return

    try:
        sessions = await env.models.session.search(
            filter=[("token", "=", token), ("active", "=", True)],
            limit=1,
            fields=["id", "user_id"],
        )
    except Exception as e:
        logger.error("WebSocket auth error: %s", e)
        return

    if not sessions:
        return

    user_id = sessions[0].user_id.id

    # accept только после успешной авторизации
    await websocket.accept()

    connected = await env.apps.chat.chat_manager.connect(websocket, user_id)
    if not connected:
        try:
            await websocket.close(code=1011, reason="Connect failed")
        except Exception as e:
            logger.warning("Failed to close a websocket: %s", e)
        return

    try:
        while True:
            data = await websocket.receive_json()
            await env.apps.chat.chat_manager.handle_message(
                websocket, user_id, data
            )
    except WebSocketDisconnect:
        logger.info("User %s disconnected", user_id)
    except Exception as e:
        logger.error(
            "WebSocket error for user %s: %s", user_id, e, exc_info=True
        )
    finally:
        await env.apps.chat.chat_manager.disconnect(websocket, user_id)
