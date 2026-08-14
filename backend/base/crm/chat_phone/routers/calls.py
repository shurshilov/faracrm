# Copyright 2025 FARA CRM
# Chat Phone module - Calls list & analytics router (telephony)
#
# Звонок = независимая модель `call` (Архитектура 2). Экран «Звонки» читает её
# напрямую (без JOIN-ов через chat_external_chat/chat_message).

import logging
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Depends, Request

from backend.base.crm.auth_token.app import AuthTokenApp

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

router_private = APIRouter(
    tags=["Telephony Calls"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


def _build_filters(
    direction: Optional[str],
    disposition: Optional[str],
    connector_id: Optional[int],
    search: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> tuple[list[str], list]:
    where = ["c.active = true"]
    params: list = []
    if direction:
        where.append("c.direction = %s")
        params.append(direction)
    if disposition:
        where.append("c.disposition = %s")
        params.append(disposition)
    if connector_id:
        where.append("c.connector_id = %s")
        params.append(connector_id)
    if date_from:
        where.append("c.started_at >= %s")
        params.append(date_from)
    if date_to:
        where.append("c.started_at <= %s")
        params.append(date_to)
    if search:
        where.append(
            "(c.number_from ILIKE %s OR c.number_to ILIKE %s "
            "OR p.name ILIKE %s)"
        )
        like = f"%{search}%"
        params.extend([like, like, like])
    return where, params


@router_private.get("/telephony/calls")
async def get_calls(
    req: Request,
    limit: int = 50,
    offset: int = 0,
    direction: Optional[str] = None,
    disposition: Optional[str] = None,
    connector_id: Optional[int] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Список звонков из реестра `call` (обогащён партнёром / коннектором / записью)."""
    env: "Environment" = req.app.state.env
    session = env.apps.db.get_session()

    where, params = _build_filters(
        direction, disposition, connector_id, search, date_from, date_to
    )
    where_sql = " AND ".join(where)

    query = f"""
        SELECT
            c.id,
            c.direction        AS call_direction,
            c.is_internal,
            c.disposition      AS call_disposition,
            c.duration         AS call_duration,
            c.duration_talk    AS call_talk_duration,
            c.started_at,
            c.number_from,
            c.number_to,
            c.connector_id,
            cc.type            AS connector_type,
            cc.name            AS connector_name,
            c.partner_id,
            p.name             AS partner_name,
            -- наша линия (endpoint/транк) и оператор
            COALESCE(pn.extension, pn.number) AS line_number,
            pn.name            AS line_name,
            u.name             AS operator_name,
            -- внешний контрагент = нога, противоположная нашей (по направлению)
            CASE WHEN c.direction = 'incoming'
                 THEN c.number_from ELSE c.number_to END AS client_number,
            a.id               AS record_id,
            c.lead_id
        FROM "call" c
        JOIN chat_connector cc ON cc.id = c.connector_id
        LEFT JOIN partners p ON p.id = c.partner_id
        LEFT JOIN phone_number pn ON pn.id = c.phone_number_id
        LEFT JOIN users u ON u.id = pn.user_id
        LEFT JOIN attachments a
            ON a.res_model = 'call'
            AND a.res_id = c.id
            AND a.mimetype = 'audio/mpeg'
        WHERE {where_sql}
        ORDER BY c.started_at DESC NULLS LAST, c.id DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    rows = await session.execute(query, params)
    return {"data": [dict(row) for row in rows]}


@router_private.get("/telephony/calls/stats")
async def get_calls_stats(
    req: Request,
    connector_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Аналитика: количество звонков по направлению и статусу."""
    env: "Environment" = req.app.state.env
    session = env.apps.db.get_session()

    where, params = _build_filters(
        None, None, connector_id, None, date_from, date_to
    )
    where_sql = " AND ".join(where)

    query = f"""
        SELECT c.direction AS direction, c.disposition AS disposition,
               COUNT(*) AS cnt
        FROM "call" c
        WHERE {where_sql}
        GROUP BY c.direction, c.disposition
    """
    rows = await session.execute(query, params)
    return {"data": [dict(row) for row in rows]}
