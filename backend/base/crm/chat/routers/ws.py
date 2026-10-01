# Copyright 2025 FARA CRM
# Chat module - WebSocket router

import logging
from typing import TYPE_CHECKING
from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.auth.exception import AuthFailed

from fastapi import Depends, APIRouter, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)

router_public = APIRouter(
    tags=["Chat WebSocket"],
    dependencies=[Depends(AuthTokenApp.use_anonymous_session)],
)


# Коды WebSocket закрытия (RFC 6455 + extensions):
#   1008 = Policy Violation (используем для auth failures)
#   1011 = Internal Server Error
_CLOSE_UNAUTHORIZED = 1008
_CLOSE_INTERNAL = 1011


@router_public.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint для real-time чата.

    Вход — как у HTTP-ручек (Token Binding): токен из query-параметра token
    плюс HttpOnly cookie сессии. Одного токена из адреса недостаточно, а
    просроченная сессия не подключится.

    ВАЖНО: по ASGI-спеке если не вызвать accept() ДО возврата, uvicorn
    выдаёт ошибку "ASGI callable returned without sending handshake".
    Поэтому на любую ошибку авторизации — accept() + close() с кодом,
    а не просто return.
    """
    token = websocket.query_params.get("token")
    env: "Environment" = websocket.app.state.env
    cookie_token = websocket.cookies.get(env.settings.auth.cookie_name)

    # Все auth-failures требуют явного accept+close, не просто return.
    # Иначе: ASGI handshake never completed → лог ошибки на каждом отказе.

    if not token or not cookie_token:
        await websocket.accept()
        await websocket.close(code=_CLOSE_UNAUTHORIZED, reason="Missing token")
        return

    try:
        session = await AuthTokenApp.check_session(env, token, cookie_token)
    except AuthFailed:
        await websocket.accept()
        await websocket.close(code=_CLOSE_UNAUTHORIZED, reason="Invalid token")
        return
    except Exception as e:
        logger.error("WebSocket auth error: %s", e)
        await websocket.accept()
        await websocket.close(
            code=_CLOSE_INTERNAL, reason="Auth lookup failed"
        )
        return

    user_id = session.user_id.id

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
