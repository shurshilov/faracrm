# Copyright 2025 FARA CRM
# Chat module - WebSocket router

import logging
from typing import TYPE_CHECKING
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)

router_public = APIRouter(tags=["Chat WebSocket"])


# Коды WebSocket закрытия (RFC 6455 + extensions):
#   1008 = Policy Violation (используем для auth failures)
#   1011 = Internal Server Error
_CLOSE_UNAUTHORIZED = 1008
_CLOSE_INTERNAL = 1011


@router_public.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint для real-time чата.

    Требует авторизации через query параметр token.

    ВАЖНО: по ASGI-спеке если не вызвать accept() ДО возврата, uvicorn
    выдаёт ошибку "ASGI callable returned without sending handshake".
    Поэтому на любую ошибку авторизации — accept() + close() с кодом,
    а не просто return.
    """
    token = websocket.query_params.get("token")
    env: "Environment" = websocket.app.state.env

    # Все auth-failures требуют явного accept+close, не просто return.
    # Иначе: ASGI handshake never completed → лог ошибки на каждом отказе.

    if not token:
        await websocket.accept()
        await websocket.close(code=_CLOSE_UNAUTHORIZED, reason="Missing token")
        return

    try:
        sessions = await env.models.session.search(
            filter=[("token", "=", token), ("active", "=", True)],
            limit=1,
            fields=["id", "user_id"],
        )
    except Exception as e:
        logger.error("WebSocket auth error: %s", e)
        await websocket.accept()
        await websocket.close(
            code=_CLOSE_INTERNAL, reason="Auth lookup failed"
        )
        return

    if not sessions:
        await websocket.accept()
        await websocket.close(code=_CLOSE_UNAUTHORIZED, reason="Invalid token")
        return

    user_id = sessions[0].user_id.id

    # accept только после успешной авторизации
    await websocket.accept()

    connected = await env.apps.chat.chat_manager.connect(websocket, user_id)
    if not connected:
        try:
            await websocket.close(
                code=_CLOSE_INTERNAL, reason="Connect failed"
            )
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
