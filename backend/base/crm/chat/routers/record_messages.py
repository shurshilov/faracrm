# Copyright 2025 FARA CRM
# Chat module - record chat router
#
# Два эндпоинта для record-чатов:
# GET  /records/{model}/{id}/chat — найти (без создания)
# POST /records/{model}/{id}/chat — get_or_create (lazy creation)
#
# Всё остальное (messages, members, reactions, pin, read) —
# через стандартные /chats/{chat_id}/... эндпоинты.

from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request

from backend.base.crm.auth_token.app import AuthTokenApp

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.sessions import Session

router_private = APIRouter(
    tags=["Record Chat"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


@router_private.get("/records/{res_model}/{res_id}/chat")
async def find_record_chat(req: Request, res_model: str, res_id: int):
    """
    Найти record-чат для записи (БЕЗ создания).

    Фронт вызывает при открытии формы. Если чат ещё не создан —
    возвращает chat_id: null. Чат создастся при первом сообщении.
    """
    env: "Environment" = req.app.state.env

    chats = await env.models.chat.search(
        filter=[
            ("res_model", "=", res_model),
            ("res_id", "=", res_id),
            ("chat_type", "=", "record"),
            ("active", "=", True),
        ],
        fields=["id", "name"],
        limit=1,
    )

    if chats:
        return {"chat_id": chats[0].id, "name": chats[0].name}

    return {"chat_id": None, "name": None}


@router_private.post("/records/{res_model}/{res_id}/chat")
async def get_or_create_record_chat(req: Request, res_model: str, res_id: int):
    """
    Получить или создать record-чат (lazy creation).

    Фронт вызывает при отправке первого сообщения или при нажатии Follow.
    Пользователь автоматически становится мембером (подписчиком).
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    chat = await env.models.chat.get_or_create_record_chat(
        res_model=res_model,
        res_id=res_id,
        user_id=user_id,
    )

    return {
        "chat_id": chat.id,
        "name": chat.name,
    }
