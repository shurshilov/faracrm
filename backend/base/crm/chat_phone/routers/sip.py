# Copyright 2025 FARA CRM
# Chat Phone module - конфиг SIP-звонилки в браузере
#
# Пароль SIP-регистрации лежит на линии (phone_number.sip_password) с
# private=True, то есть в обычный CRUD он не попадает никогда. Отдать его можно
# только здесь и только владельцу линии — это единственная ручка, знающая пароль.

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Request,
    WebSocket,
)
from websockets.asyncio.client import connect as ws_connect
from websockets.typing import Subprotocol

from backend.base.crm.auth_token.app import AuthTokenApp

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

router_private = APIRouter(
    tags=["Telephony SIP"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)

# Прокси-сокет авторизуется сам (токеном в query), как /ws/chat.
router_public = APIRouter(
    tags=["Telephony SIP"],
    dependencies=[Depends(AuthTokenApp.use_anonymous_session(["sessions"]))],
)

UNAVAILABLE = {
    "available": False,
    "has_line": False,
    "has_transport": False,
    "has_password": False,
}

# Коды закрытия WebSocket (как в chat/routers/ws.py).
_CLOSE_UNAUTHORIZED = 1008
_CLOSE_UNAVAILABLE = 1011


async def _my_line(env: "Environment", user_id: int):
    """
    Линия сотрудника вместе с нужными полями коннектора — ОДНИМ запросом.

    private=True прячет sip_password только из API-схемы, ORM его читает как
    любое store-поле, поэтому отдельный SQL за паролем не нужен.
    """
    rows = await env.models.phone_number.search(
        filter=[("user_id", "=", user_id), ("active", "=", True)],
        fields=["id", "extension", "number", "sip_password", "connector_id"],
        fields_nested={
            "connector_id": ["id", "sip_ws_url", "sip_realm", "sip_ice"]
        },
        limit=1,
    )
    return rows[0] if rows else None


@router_private.get("/telephony/sip/config")
async def get_sip_config(req: Request):
    """
    Настройки звонилки для ТЕКУЩЕГО пользователя.

    Отвечаем всегда 200 и отдельными флагами говорим, ЧЕГО не хватает: кнопка в
    шапке видна всегда, и по клику показывает пользователю, что именно
    настроить. Молчаливое available=False заставляло бы гадать.
    """
    env: "Environment" = req.app.state.env
    user_id = req.state.session.user_id.id

    line = await _my_line(env, user_id)
    if not line:
        return {"data": UNAVAILABLE}

    connector = line.connector_id
    password = line.sip_password
    transport = connector.sip_ws_url
    ready = bool(transport and password)

    # Адрес АТС наружу НЕ отдаём: браузер ходит на наш же /ws/sip, а тот уже
    # знает, куда переслать. Фронт собирает адрес из своего origin.
    ice = connector.sip_ice or ""
    return {
        "data": {
            "available": ready,
            "has_line": True,
            "has_transport": bool(transport),
            "has_password": bool(password),
            "realm": connector.sip_realm or "",
            "ice": [s.strip() for s in ice.split(",") if s.strip()],
            "extension": line.extension or line.number or "",
            "password": password if ready else None,
        }
    }


@router_private.put("/telephony/sip/password/{phone_number_id}")
async def set_sip_password(
    req: Request, phone_number_id: int, password: str = Body(..., embed=True)
):
    """
    Задать пароль линии: private-поле в generic-форму не приезжает, поэтому
    пишем его отдельной ручкой.

    Пишем через ORM, а не прямым SQL: тогда права проверяет сам движок
    (phone_number правит админ, у остальных read-only) — вместо ручной проверки,
    которая не знала бы про роли и record-rules.
    """
    env: "Environment" = req.app.state.env

    rows = await env.models.phone_number.search(
        filter=[("id", "=", phone_number_id)], fields=["id"], limit=1
    )
    if not rows:
        raise HTTPException(status_code=404, detail="PHONE_NUMBER_NOT_FOUND")

    await rows[0].update(
        env.models.phone_number(sip_password=password or None)
    )
    return {"data": {"ok": True}}


@router_public.websocket("/ws/sip")
async def sip_ws_proxy(websocket: WebSocket):
    """
    Прокси SIP-сокета: браузер ↔ ФАРА ↔ АТС.

    Зачем: браузеру запрещено ходить на чужой домен (CSP разрешает только наш),
    а адрес АТС хранится в настройках коннектора — значит менять его можно из
    интерфейса, не трогая конфиг nginx. Путь /ws/* уже проксируется с
    Upgrade-семантикой и в проде, и в dev.

    ЗВУК здесь не идёт: RTP/DTLS согласуется напрямую браузер ↔ АТС. Через нас
    проходят только SIP-сообщения — их мало, и они текстовые.
    """
    env: "Environment" = websocket.app.state.env
    token = websocket.query_params.get("token")

    # Любой отказ требует accept+close: без accept ASGI ругается на
    # незавершённый handshake (см. chat/routers/ws.py).
    if not token:
        await websocket.accept()
        await websocket.close(_CLOSE_UNAUTHORIZED, "Missing token")
        return

    sessions = await env.models.session.search(
        filter=[("token", "=", token), ("active", "=", True)],
        fields=["id", "user_id"],
        limit=1,
    )
    if not sessions:
        await websocket.accept()
        await websocket.close(_CLOSE_UNAUTHORIZED, "Invalid token")
        return

    line = await _my_line(env, sessions[0].user_id.id)
    url = line.connector_id.sip_ws_url if line else None
    if not url:
        await websocket.accept()
        await websocket.close(_CLOSE_UNAVAILABLE, "SIP not configured")
        return

    # JsSIP и Asterisk договариваются по субпротоколу 'sip' — эхо обязательно,
    # иначе браузер разорвёт соединение сразу после рукопожатия.
    await websocket.accept(subprotocol="sip")
    try:
        async with ws_connect(url, subprotocols=[Subprotocol("sip")]) as pbx:
            await _pipe(websocket, pbx)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[sip] прокси к %s оборвался: %s", url, exc)
        await websocket.close(_CLOSE_UNAVAILABLE, "PBX unreachable")


async def _pipe(browser: WebSocket, pbx) -> None:
    """Перекладывать кадры в обе стороны, пока жива любая из сторон."""

    async def to_pbx() -> None:
        while True:
            message = await browser.receive()
            if message["type"] == "websocket.disconnect":
                return
            text = message.get("text")
            await pbx.send(text if text is not None else message["bytes"])

    async def to_browser() -> None:
        async for frame in pbx:
            if isinstance(frame, str):
                await browser.send_text(frame)
            else:
                await browser.send_bytes(frame)

    tasks = [asyncio.create_task(to_pbx()), asyncio.create_task(to_browser())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
