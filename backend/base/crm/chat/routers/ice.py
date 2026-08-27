# Copyright 2025 FARA CRM
# Chat module - ICE/TURN endpoints
#
# ЕДИНАЯ точка выдачи ICE-конфига на все виды звонков:
#   - внутренние WebRTC сотрудник↔сотрудник (chat/routers/calls.py),
#   - звонилка в браузере к АТС (chat_phone/routers/sip.py).
# Живёт в chat, а не в chat_phone: модуль chat есть всегда, и от него зависит
# телефония, а не наоборот.
#
# Endpoints:
#   GET  /ice/servers  → { ice_servers, ice_transport_policy, ttl }
#   POST /ice/test     → { ok, error, mapped_address, relayed_address }

import logging
import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.status import HTTP_403_FORBIDDEN, HTTP_429_TOO_MANY_REQUESTS

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.chat.turn import (
    build_ice_config,
    host_from_request,
    probe,
    resolve_settings,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

router_private = APIRouter(
    tags=["Telephony ICE"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)

# Антидребезг проверки. Каждая проверка — это настоящая аллокация на релее из
# узкого диапазона портов, поэтому «зажатая кнопка» не должна выедать его.
# Счётчик процессный (воркеров несколько), но задача не в точном лимите, а в
# том, чтобы порядок величин не улетал.
_TEST_MIN_INTERVAL = 3.0
_last_test_at = 0.0


@router_private.get("/ice/servers")
async def get_ice_servers(req: Request):
    """
    ICE-серверы для ТЕКУЩЕГО пользователя.

    Креды временные, поэтому ручка вызывается перед каждым звонком, а не один
    раз при загрузке приложения. Ответ всегда 200: если релей не настроен,
    отдаём STUN-фоллбэк — звонки в дружественных сетях продолжают работать.
    """
    env: "Environment" = req.app.state.env
    user_id = req.state.session.user_id.id
    settings = await resolve_settings(env, host_from_request(req))
    return {"data": build_ice_config(settings, user_id)}


@router_private.post("/ice/test")
async def test_ice(req: Request):
    """
    Проверить релей вживую (кнопка «Проверить релей» в настройках).

    Делаем настоящую аллокацию с настоящими кредами: это отвечает не «порт
    открыт», а «звонок через релей пойдёт».

    Только для администратора: ручка ходит в сеть и занимает ресурс на релее,
    а рядовому пользователю она ничего не объясняет — чинить всё равно админу.
    """
    global _last_test_at

    env: "Environment" = req.app.state.env
    if not getattr(req.state.session.user_id, "is_admin", False):
        raise HTTPException(HTTP_403_FORBIDDEN, "ADMIN_REQUIRED")

    now = time.monotonic()
    if now - _last_test_at < _TEST_MIN_INTERVAL:
        raise HTTPException(HTTP_429_TOO_MANY_REQUESTS, "TOO_FREQUENT")
    _last_test_at = now

    settings = await resolve_settings(env, host_from_request(req))
    return {"data": await probe(settings)}
