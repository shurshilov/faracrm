# Copyright 2025 FARA CRM
# Payment module - уведомления провайдеров об оплате

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.payment.strategies import get_provider

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)

# Подпись уведомления проверяет сам провайдер (handle_notification),
# платёж меняется от системной сессии — как чат-вебхуки.
router_public = APIRouter(
    tags=["Payment"],
    dependencies=[Depends(AuthTokenApp.use_system_session)],
)


@router_public.post("/payments/webhook/{provider_type}")
async def payment_webhook(req: Request, provider_type: str):
    env: "Environment" = req.app.state.env
    provider = get_provider(provider_type)
    payload = await req.json()
    external_id, state = await provider.handle_notification(payload)

    async with env.apps.db.get_transaction():
        payments = await env.models.payment.search(
            filter=[
                ("provider", "=", provider_type),
                ("external_id", "=", external_id),
            ],
            limit=1,
        )
        if not payments:
            # Неизвестный платёж: отвечаем «принято», иначе провайдер будет
            # слать уведомление повторно.
            logger.warning(
                "Payment webhook %s: unknown payment %s",
                provider_type,
                external_id,
            )
        elif state == "paid":
            await payments[0].mark_paid()
        elif state == "failed":
            await payments[0].mark_failed()

    return PlainTextResponse(provider.notification_response)
