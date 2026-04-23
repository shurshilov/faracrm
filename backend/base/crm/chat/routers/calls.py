# Copyright 2025 FARA CRM
# Chat module - WebRTC calls router (1-на-1 аудио)
#
# Архитектура:
#   - Звонок = ChatMessage с message_type='call' в direct-чате между
#     двумя юзерами. Поля звонка задаются ChatMessagePhoneMixin из
#     модуля chat_phone (call_direction, call_disposition, ...).
#   - Сигналинг (SDP/ICE) идёт через существующий WebSocket чата.
#     Этот роутер создаёт запись звонка, делает presence-check,
#     и обновляет статус (accept/reject/end).
#   - Голосовой трафик идёт peer-to-peer через WebRTC (STUN от Google).
#
# Endpoints:
#   POST /calls/start         { callee_user_id }      → { call_id, chat_id, callee }
#                             409 если callee оффлайн (не ответил ack за 3 сек)
#   POST /calls/{id}/accept                           → { ok }
#   POST /calls/{id}/reject                           → { ok }
#   POST /calls/{id}/end      { duration_seconds? }   → { ok }

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.status import (
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from backend.base.crm.auth_token.app import AuthTokenApp

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.sessions import Session

router_private = APIRouter(
    tags=["Chat Calls"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)

# Таймаут ожидания ack от callee перед тем, как считать его оффлайн.
# 3 секунды — компромисс: меньше — ложные срабатывания для юзеров
# с медленной сетью; больше — длинная задержка при "не в сети".
_INVITE_ACK_TIMEOUT = 3.0


# ─── Schemas ──────────────────────────────────────────────────────


class CallStartPayload(BaseModel):
    callee_user_id: int


class CallEndPayload(BaseModel):
    duration_seconds: int | None = None


# ─── Helpers ──────────────────────────────────────────────────────


async def _load_call_or_404(env: "Environment", call_id: int):
    """Загрузить ChatMessage(type='call') или бросить 404."""
    try:
        msg = await env.models.chat_message.search(
            filter=[("id", "=", call_id)], limit=1
        )
    except Exception:
        raise HTTPException(HTTP_404_NOT_FOUND, "Call not found")
    if not msg or msg[0].message_type != "call":
        raise HTTPException(HTTP_404_NOT_FOUND, "Not a call message")
    return msg[0]


async def _find_other_user(env, chat_id: int, not_user_id: int) -> int | None:
    """Найти второго участника direct-чата (не равного not_user_id)."""
    members = await env.models.chat_member.search(
        filter=[
            ("chat_id", "=", chat_id),
            ("is_active", "=", True),
        ],
        fields=["user_id"],
        limit=5,
    )
    for m in members:
        uid = m.user_id.id if hasattr(m.user_id, "id") else m.user_id
        if uid and uid != not_user_id:
            return uid
    return None


async def _assert_participant(env, chat_id: int, user_id: int):
    """Проверить что user_id — участник direct-чата звонка."""
    members = await env.models.chat_member.search(
        filter=[
            ("chat_id", "=", chat_id),
            ("user_id", "=", user_id),
            ("is_active", "=", True),
        ],
        fields=["id"],
        limit=1,
    )
    if not members:
        raise HTTPException(
            HTTP_403_FORBIDDEN, "Not a participant of this call"
        )


def _is_terminal(disposition: str | None) -> bool:
    """Звонок уже завершён? Блокирует повторные accept/reject/end."""
    return disposition in (
        "answered",
        "no_answer",
        "busy",
        "failed",
        "cancelled",
    )


def _serialize_call_message(msg, author_name: str | None = None) -> dict:
    """
    Сериализовать ChatMessage(type='call') в формат, который фронт
    ожидает для типа `new_message` / `message_updated`.

    Формат совместим с `/chats/.../messages` POST-ответом, чтобы фронт
    мог показывать call-плашку через тот же `CallMessageContent`.
    """
    author = None
    if msg.author_user_id:
        author = {
            "id": msg.author_user_id.id,
            "name": author_name
            or getattr(msg.author_user_id, "name", None)
            or "",
            "type": "user",
        }
    return {
        "id": msg.id,
        "body": msg.body or "",
        "message_type": "call",
        "author": author,
        "create_date": (
            msg.create_date.isoformat() if msg.create_date else None
        ),
        "starred": bool(msg.starred),
        "pinned": bool(msg.pinned),
        "is_edited": bool(msg.is_edited),
        "is_read": False,
        "attachments": [],
        # Call-поля
        "call_direction": msg.call_direction,
        "call_disposition": msg.call_disposition,
        "call_duration": msg.call_duration,
        "call_talk_duration": msg.call_talk_duration,
        "call_answer_time": (
            msg.call_answer_time.isoformat()
            if isinstance(msg.call_answer_time, datetime)
            else None
        ),
        "call_end_time": (
            msg.call_end_time.isoformat()
            if isinstance(msg.call_end_time, datetime)
            else None
        ),
    }


async def _broadcast_new_call_message(
    env, chat_id: int, msg, author_name: str
):
    """Уведомить подписчиков чата о создании нового call-сообщения."""
    await env.apps.chat.chat_manager.send_to_chat(
        chat_id=chat_id,
        message={
            "type": "new_message",
            "chat_id": chat_id,
            "message": _serialize_call_message(msg, author_name),
        },
    )


async def _broadcast_call_message_updated(env, chat_id: int, msg):
    """Уведомить подписчиков об обновлении call-сообщения (смена статуса)."""
    await env.apps.chat.chat_manager.send_to_chat(
        chat_id=chat_id,
        message={
            "type": "message_updated",
            "chat_id": chat_id,
            "message": _serialize_call_message(msg),
        },
    )


# ─── Endpoints ────────────────────────────────────────────────────


@router_private.post("/calls/start")
async def start_call(req: Request, payload: CallStartPayload):
    """
    Начать звонок пользователю (1-на-1, аудио).

    Flow:
      1. Создаём/находим direct-чат между caller и callee.
      2. Создаём ChatMessage(type='call', disposition='ringing').
      3. Шлём callee invite через WebSocket (cross-process).
      4. Ждём ack от callee до _INVITE_ACK_TIMEOUT (presence-check).
      5. Если ack пришёл → возвращаем 200. Если нет → 409 (offline).
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    caller_id = auth_session.user_id.id

    callee_id = payload.callee_user_id
    if callee_id == caller_id:
        raise HTTPException(400, "Cannot call yourself")

    # Проверяем существование callee
    try:
        callee = await env.models.user.get(callee_id)
    except Exception:
        raise HTTPException(HTTP_404_NOT_FOUND, "Callee not found")

    # Находим/создаём direct-чат
    chat = await env.models.chat.create_direct_chat(caller_id, callee_id)

    # Создаём call-сообщение
    now = datetime.now(timezone.utc)
    msg = env.models.chat_message(
        body="",  # UI сам отрисует плашку по полям call_*
        message_type="call",
        chat_id=chat,
        author_user_id=auth_session.user_id,
        call_direction="outgoing",
        call_disposition="ringing",
        create_date=now,
        write_date=now,
    )
    msg.id = await env.models.chat_message.create(payload=msg)

    # Обновляем дату последнего сообщения чата — это важно для того,
    # чтобы чат со звонком поднялся вверх в списке (такая же логика,
    # как в post_message). Без этого last_message_date остаётся старой
    # и call-сообщение считается "старше" последнего обычного.
    await chat.update_last_message_date()

    # Оповещаем подписчиков чата, что появилось новое call-сообщение,
    # чтобы UI обоих юзеров сразу показал плашку "Исходящий звонок...".
    # Без этого обычный /chats/{id}/messages не рефрешится до ручного запроса.
    await _broadcast_new_call_message(
        env, chat.id, msg, auth_session.user_id.name
    )

    # Регистрируем pending-event и шлём invite получателю
    chat_manager = env.apps.chat.chat_manager
    ack_event = chat_manager._register_pending_invite(msg.id)

    try:
        caller_data = {
            "id": auth_session.user_id.id,
            "name": auth_session.user_id.name,
        }
        await chat_manager.send_to_user(
            callee_id,
            {
                "type": "call.invite",
                "call_id": msg.id,
                "chat_id": chat.id,
                "caller": caller_data,
            },
        )

        # Ждём ack от callee.
        try:
            await asyncio.wait_for(
                ack_event.wait(), timeout=_INVITE_ACK_TIMEOUT
            )
        except asyncio.TimeoutError:
            # Callee оффлайн или не отвечает. Помечаем звонок failed.
            now2 = datetime.now(timezone.utc)
            await msg.update(
                env.models.chat_message(
                    call_disposition="failed",
                    call_end_time=now2,
                    write_date=now2,
                )
            )
            raise HTTPException(HTTP_409_CONFLICT, "Callee is offline")
    finally:
        chat_manager._cleanup_pending_invite(msg.id)

    return {
        "call_id": msg.id,
        "chat_id": chat.id,
        "callee": {"id": callee.id, "name": callee.name},
    }


@router_private.post("/calls/{call_id}/accept")
async def accept_call(req: Request, call_id: int):
    """
    Callee принял звонок. Обновляет disposition='answered',
    уведомляет caller через WebSocket.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    msg = await _load_call_or_404(env, call_id)
    chat_id = msg.chat_id.id

    await _assert_participant(env, chat_id, user_id)

    # Только callee может принять (не автор call-сообщения).
    caller_id = msg.author_user_id.id if msg.author_user_id else None
    if user_id == caller_id:
        raise HTTPException(HTTP_403_FORBIDDEN, "Only callee can accept")

    if _is_terminal(msg.call_disposition):
        raise HTTPException(HTTP_409_CONFLICT, "Call already finalized")

    now = datetime.now(timezone.utc)
    await msg.update(
        env.models.chat_message(
            call_disposition="answered",
            call_answer_time=now,
            write_date=now,
        )
    )

    # Уведомляем caller.
    await env.apps.chat.chat_manager.send_to_user(
        caller_id,
        {"type": "call.accepted", "call_id": call_id},
    )

    return {"ok": True}


@router_private.post("/calls/{call_id}/reject")
async def reject_call(req: Request, call_id: int):
    """
    Отклонить или отменить звонок:
      - если reject делает callee → disposition='no_answer'
      - если reject делает caller → disposition='cancelled'
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    msg = await _load_call_or_404(env, call_id)
    chat_id = msg.chat_id.id

    await _assert_participant(env, chat_id, user_id)

    if _is_terminal(msg.call_disposition):
        raise HTTPException(HTTP_409_CONFLICT, "Call already finalized")

    caller_id = msg.author_user_id.id if msg.author_user_id else None
    is_caller = user_id == caller_id

    now = datetime.now(timezone.utc)
    await msg.update(
        env.models.chat_message(
            call_disposition="cancelled" if is_caller else "no_answer",
            call_end_time=now,
            write_date=now,
        )
    )

    # Уведомляем "другую" сторону.
    other_id = await _find_other_user(env, chat_id, user_id)
    if other_id:
        await env.apps.chat.chat_manager.send_to_user(
            other_id,
            {
                "type": "call.rejected",
                "call_id": call_id,
                "reason": "cancelled" if is_caller else "declined",
            },
        )

    return {"ok": True}


@router_private.post("/calls/{call_id}/end")
async def end_call(req: Request, call_id: int, payload: CallEndPayload):
    """
    Завершить активный звонок (hangup).
    Обновляет call_end_time и длительность.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    msg = await _load_call_or_404(env, call_id)
    chat_id = msg.chat_id.id

    await _assert_participant(env, chat_id, user_id)

    now = datetime.now(timezone.utc)

    # Считаем длительность
    call_duration = int((now - msg.create_date).total_seconds())
    call_talk_duration = None
    if msg.call_answer_time:
        call_talk_duration = int((now - msg.call_answer_time).total_seconds())

    # Если клиент прислал свою длительность — уважаем (точнее client-side)
    if payload.duration_seconds is not None and payload.duration_seconds >= 0:
        call_talk_duration = payload.duration_seconds

    # Если звонок был answered — disposition остаётся 'answered'.
    # Если не был — ставим 'no_answer' (разговор не состоялся).
    new_disposition = msg.call_disposition
    if new_disposition == "ringing":
        new_disposition = "no_answer"

    await msg.update(
        env.models.chat_message(
            call_disposition=new_disposition,
            call_end_time=now,
            call_duration=call_duration,
            call_talk_duration=call_talk_duration,
            write_date=now,
        )
    )

    # Уведомляем обе стороны (оба UI закроют виджет).
    caller_id = msg.author_user_id.id if msg.author_user_id else None
    other_id = await _find_other_user(env, chat_id, caller_id or user_id)
    for uid in (caller_id, other_id):
        if uid:
            await env.apps.chat.chat_manager.send_to_user(
                uid,
                {
                    "type": "call.end",
                    "call_id": call_id,
                    "duration": call_talk_duration or 0,
                },
            )

    return {"ok": True}
