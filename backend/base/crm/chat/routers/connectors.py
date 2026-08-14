# Copyright 2025 FARA CRM
# Chat module - connectors router (специфичные endpoints)
#
# CRUD операции (create, read, update, delete) обрабатываются автоматически
# через dotorm_crud_auto. Этот роутер содержит только специфичную логику:
# - webhook управление (set/unset/info)
# - типы коннекторов
#
# Webhook callback endpoint находится в webhook.py

from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, Body, Depends, Request
from pydantic import AwareDatetime

from backend.base.crm.auth_token.app import AuthTokenApp

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.security.models.sessions import Session


router_private = APIRouter(
    tags=["Chat Connectors"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


# ============================================================================
# Webhook управление
# ============================================================================


@router_private.post("/connectors/{connector_id}/webhook/set")
async def set_connector_webhook(req: Request, connector_id: int):
    """
    Установить webhook для коннектора.

    Отправляет запрос к внешнему API (например, Telegram)
    для регистрации webhook URL.
    """
    env: "Environment" = req.app.state.env

    connector = await env.models.chat_connector.get(connector_id)

    # api_url берётся из SystemSettings (core.api_url) внутри set_webhook.
    # Ранее здесь использовался str(req.base_url) — ненадёжно за nginx:
    # он зависит от X-Forwarded-Host/Proto и может не совпадать с тем,
    # что зарегистрировано в Telegram.
    success = await connector.set_webhook()

    return {
        "success": success,
        "webhook_state": connector.webhook_state,
        "webhook_url": connector.webhook_url,
        "webhook_hash": connector.webhook_hash,
    }


@router_private.post("/connectors/{connector_id}/webhook/unset")
async def unset_connector_webhook(req: Request, connector_id: int):
    """
    Удалить webhook коннектора.

    Отправляет запрос к внешнему API для удаления webhook.
    """
    env: "Environment" = req.app.state.env

    connector = await env.models.chat_connector.get(connector_id)

    success = await connector.unset_webhook()

    return {"success": success, "webhook_state": connector.webhook_state}


@router_private.post("/connectors/{connector_id}/webhook/delete-by-url")
async def delete_connector_webhook_by_url(req: Request, connector_id: int):
    """
    Удалить подписку/webhook по ПРОИЗВОЛЬНОМУ URL (не только текущему
    connector.webhook_url) — для чистки старых подписок.

    Тело: {"url": "<webhook_url>"}. Поддерживается провайдерами со списком
    подписок (MAX). Для остальных стратегия бросит NotImplementedError.
    """
    env: "Environment" = req.app.state.env

    payload = await req.json()
    webhook_url = (payload or {}).get("url")
    if not webhook_url:
        return {"data": {"ok": False, "error": "url required"}}

    connector = await env.models.chat_connector.get(connector_id)
    try:
        result = await connector.strategy.delete_webhook_by_url(
            connector, webhook_url
        )
    except NotImplementedError as e:
        return {"data": {"ok": False, "error": str(e)}}
    return {"data": {"ok": True, "result": result}}


@router_private.get("/connectors/{connector_id}/webhook/info")
async def get_connector_webhook_info(req: Request, connector_id: int):
    """
    Получить информацию о webhook от внешнего API.

    Возвращает текущее состояние webhook по данным провайдера.
    """
    env: "Environment" = req.app.state.env

    connector = await env.models.chat_connector.get(connector_id)

    info = await connector.strategy.get_webhook_info(connector)

    return {"data": info}


@router_private.post("/connectors/{connector_id}/test")
async def test_connector_connection(req: Request, connector_id: int):
    """
    Проверить соединение коннектора по текущим настройкам.

    Для Email — логин по SMTP/IMAP: пользователь сразу видит, верны
    ли сервер и пароль. Для типов без поддержки проверки возвращает
    ok=false с пояснением (см. ChatStrategyBase.test_connection).
    """
    env: "Environment" = req.app.state.env

    connector = await env.models.chat_connector.get(connector_id)

    result = await connector.strategy.test_connection(connector)
    return {"data": result}


@router_private.post("/connectors/{connector_id}/sync-numbers")
async def sync_connector_numbers(req: Request, connector_id: int):
    """
    Синхронизировать номера / операторские линии из АТС.
    """
    env: "Environment" = req.app.state.env

    connector = await env.models.chat_connector.get(connector_id)

    result = await connector.strategy.sync_numbers(connector, env)
    return {"data": result}


@router_private.post("/connectors/{connector_id}/fetch-history")
async def fetch_connector_history(
    req: Request,
    connector_id: int,
    start: AwareDatetime = Body(...),
    end: AwareDatetime = Body(...),
    mode: Literal["normal", "no_notify", "silent"] = Body("silent"),
):
    """
    Прочитать историю звонков из CDR за период [start, end] и импортировать
    (создать call-сообщения). start/end — timezone-aware даты (валидируются
    Pydantic; из фронта уходят как ISO-строки с зоной).

    mode — как обрабатывать исторические звонки (по умолчанию silent):
    normal (как живой звонок: попап + лид) / no_notify (без попапа) /
    silent (без попапа и без лида — только сообщение).

    Для Asterisk: тянет CDR через источник и прогоняет каждую запись через
    пайплайн. Для типов без поддержки — ok=false (см. базовый
    ChatStrategyBase.import_history).
    """
    env: "Environment" = req.app.state.env

    connector = await env.models.chat_connector.get(connector_id)

    result = await connector.strategy.import_history(
        connector, start, end, env, mode=mode
    )
    return {"data": result}


@router_private.post("/connectors/{connector_id}/listener/start")
async def start_connector_listener(req: Request, connector_id: int):
    """
    Включить постоянный in-process слушатель событий (Asterisk ARI, local-режим).

    Проверяет соединение и, только если прошло, поднимает слушатель + ставит флаг
    автозапуска. Возвращает {"ok", "enabled", "message"}.
    """
    env: "Environment" = req.app.state.env

    connector = await env.models.chat_connector.get(connector_id)

    result = await connector.strategy.set_listener(connector, True, env)
    return {"data": result}


@router_private.post("/connectors/{connector_id}/listener/stop")
async def stop_connector_listener(req: Request, connector_id: int):
    """Выключить постоянный слушатель событий (снимает флаг автозапуска)."""
    env: "Environment" = req.app.state.env

    connector = await env.models.chat_connector.get(connector_id)

    result = await connector.strategy.set_listener(connector, False, env)
    return {"data": result}


@router_private.get("/connectors/{connector_id}/account/self")
async def get_connector_self_account(req: Request, connector_id: int):
    """
    Получить информацию об аккаунте от внешнего сервиса.

    Используется в форме настройки коннектора, чтобы вытащить
    `external_account_id` из API провайдера (например, Avito возвращает
    {id, name, email, phone, profile_url}).
    """

    env: "Environment" = req.app.state.env

    connector = await env.models.chat_connector.get(connector_id)

    info = await connector.strategy.get_self_account_id(connector)
    return {"data": info}


# ============================================================================
# Мои коннекторы (для sidebar)
# ============================================================================


@router_private.get("/connectors/my")
async def get_my_connectors(req: Request):
    """
    Активные коннекторы, где текущий пользователь — руководитель.

    Возвращает уникальные типы коннекторов для построения
    динамического меню в ChatSidebar.
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    session = env.apps.db.get_session()
    query = """
        SELECT DISTINCT cc.type, cc.name
        FROM chat_connector cc
        JOIN chat_connector_manager_many2many m
            ON m.connector_id = cc.id
        WHERE cc.active = true
            AND m.user_id = %s
        ORDER BY cc.type
    """
    result = await session.execute(query, [user_id])

    return {
        "data": [{"type": row["type"], "name": row["name"]} for row in result]
    }
