# Copyright 2025 FARA CRM
# Chat Phone module - конфиг SIP-звонилки в браузере
#
# Пароль SIP-регистрации лежит на линии (phone_number.sip_password) и правится
# на форме номера. Здесь он отдаётся браузеру — но только ВЛАДЕЛЬЦУ линии и
# только вместе с остальным конфигом звонилки.

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import (
    APIRouter,
    Depends,
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

# Коды закрытия WebSocket (как в chat/routers/ws.py).
_CLOSE_UNAUTHORIZED = 1008
_CLOSE_UNAVAILABLE = 1011


async def _my_lines(env: "Environment", user_id: int) -> dict:
    """
    Линии сотрудника по коннекторам: {connector_id: линия}.

    Линий может быть несколько — по одной в каждом коннекторе телефонии,
    поэтому доступность считаем ДЛЯ КАЖДОГО канала отдельно, а не выбираем
    одну «свою». sip_password правится на форме номера, ORM
    читает его как обычное store-поле — отдельный SQL за паролем не нужен.
    """
    rows = await env.models.phone_number.search(
        filter=[("user_id", "=", user_id), ("active", "=", True)],
        fields=["id", "extension", "number", "sip_password", "connector_id"],
    )
    return {row.connector_id.id: row for row in rows if row.connector_id}


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

    # Телефонные каналы показываем ВСЕ и всегда: выбор канала — это способ
    # узнать, чего ему не хватает. Доступность считаем для КАЖДОГО отдельно:
    # линий у сотрудника может быть несколько, по одной в разных коннекторах.
    connectors = await env.models.chat_connector.search(
        filter=[("category", "=", "phone"), ("active", "=", True)],
        fields=["id", "name", "sip_ws_url", "sip_realm", "sip_ice"],
        sort="id",
        order="ASC",
    )
    lines = await _my_lines(env, user_id)

    channels = []
    for connector in connectors:
        line = lines.get(connector.id)
        password = line.sip_password if line else None
        transport = connector.sip_ws_url
        ready = bool(transport and password)
        ice = connector.sip_ice or ""
        channels.append(
            {
                "id": connector.id,
                "name": connector.name or "Телефония",
                "available": ready,
                "has_transport": bool(transport),
                "has_line": bool(line),
                "has_password": bool(password),
                "extension": (
                    (line.extension or line.number or "") if line else ""
                ),
                "realm": connector.sip_realm or "",
                "ice": [s.strip() for s in ice.split(",") if s.strip()],
                # Адрес АТС наружу НЕ отдаём: браузер ходит на наш же /ws/sip,
                # а тот уже знает, куда переслать.
                "password": password if ready else None,
            }
        )

    return {"data": {"channels": channels}}


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

    # Каким коннектором регистрируемся — говорит браузер. Проверяем, что линия
    # сотрудника в нём действительно есть: иначе через нас можно было бы
    # достучаться до любой чужой АТС.
    connector_id = int(websocket.query_params.get("connector") or 0)
    lines = await _my_lines(env, sessions[0].user_id.id)
    url = None
    if connector_id in lines:
        connector = await env.models.chat_connector.get(connector_id)
        url = connector.sip_ws_url

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
