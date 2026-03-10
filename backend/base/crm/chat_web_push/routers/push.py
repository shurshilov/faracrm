# Copyright 2025 FARA CRM
# Chat Web Push module - subscription router

import json
import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.base.crm.auth_token.app import AuthTokenApp

logger = logging.getLogger(__name__)

router_private = APIRouter(
    prefix="/web-push",
    tags=["Web Push"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


class PushSubscriptionData(BaseModel):
    endpoint: str
    keys: dict


class PushSubscriptionResponse(BaseModel):
    success: bool
    message: str = ""


@router_private.post("/subscribe", response_model=PushSubscriptionResponse)
async def subscribe(req: Request, body: PushSubscriptionData):
    env = req.app.state.env
    auth_session = req.state.session
    user_id = auth_session.user_id.id

    subscription_json = json.dumps(
        {
            "endpoint": body.endpoint,
            "keys": body.keys,
        }
    )

    contact_type = await env.models.contact_type.search(
        filter=[("name", "=", "web_push")],
        fields=["id"],
        limit=1,
    )

    if not contact_type:
        logger.error("[web_push] Contact type web_push not found.")
        return PushSubscriptionResponse(
            success=False,
            message="Web Push contact type not configured",
        )

    contact_type_id = contact_type[0].id

    # Макс подписок на пользователя (разные браузеры/устройства)
    MAX_SUBSCRIPTIONS = 5

    existing = await env.models.contact.search(
        filter=[
            ("user_id", "=", user_id),
            ("contact_type_id", "=", contact_type_id),
            ("active", "=", True),
        ],
        order="ASC",
        sort="id",
    )

    # Ищем контакт с тем же endpoint — обновляем ключи
    for contact in existing:
        try:
            data = json.loads(contact.name)
            if data.get("endpoint") == body.endpoint:
                await contact.update(
                    env.models.contact(name=subscription_json)
                )
                logger.info(
                    "[web_push] Updated subscription for user %s", user_id
                )
                return PushSubscriptionResponse(
                    success=True, message="Subscription updated"
                )
        except (json.JSONDecodeError, TypeError):
            # Битый JSON — деактивируем мусорный контакт
            await contact.update(env.models.contact(active=False))
            logger.warning(
                "[web_push] Deactivated broken contact %s", contact.id
            )

    # Пересчитаем после возможной деактивации битых
    valid_count = sum(
        1 for c in existing if c.active  # после update объект ещё в списке
    )

    # Если лимит достигнут — деактивируем самую старую подписку
    if valid_count >= MAX_SUBSCRIPTIONS:
        oldest = existing[0]
        await oldest.update(env.models.contact(active=False))
        logger.info(
            "[web_push] Evicted oldest subscription %s for user %s",
            oldest.id,
            user_id,
        )

    await env.models.contact.create(
        env.models.contact(
            user_id=auth_session.user_id,
            contact_type_id=contact_type[0],
            name=subscription_json,
            is_primary=len(existing) == 0,
        )
    )

    logger.info("[web_push] Created subscription for user %s", user_id)
    return PushSubscriptionResponse(
        success=True, message="Subscribed successfully"
    )


@router_private.post("/unsubscribe", response_model=PushSubscriptionResponse)
async def unsubscribe(req: Request, body: PushSubscriptionData):
    env = req.app.state.env
    auth_session = req.state.session
    user_id = auth_session.user_id.id

    contact_type = await env.models.contact_type.search(
        filter=[("name", "=", "web_push")],
        fields=["id"],
        limit=1,
    )

    if not contact_type:
        return PushSubscriptionResponse(
            success=False, message="Not configured"
        )

    contacts = await env.models.contact.search(
        filter=[
            ("user_id", "=", user_id),
            ("contact_type_id", "=", contact_type[0].id),
            ("active", "=", True),
        ],
    )

    for contact in contacts:
        try:
            data = json.loads(contact.name)
            if data.get("endpoint") == body.endpoint:
                await contact.update(env.models.contact(active=False))
                logger.info("[web_push] Unsubscribed user %s", user_id)
                return PushSubscriptionResponse(
                    success=True, message="Unsubscribed"
                )
        except (json.JSONDecodeError, TypeError):
            continue

    return PushSubscriptionResponse(
        success=False, message="Subscription not found"
    )


@router_private.get("/vapid-key")
async def get_vapid_public_key(req: Request):
    env = req.app.state.env

    connector = await env.models.chat_connector.search(
        filter=[
            ("type", "=", "web_push"),
            ("active", "=", True),
        ],
        fields=["client_app_id"],
        limit=1,
    )

    if not connector:
        return {"vapid_public_key": None}

    return {"vapid_public_key": connector[0].client_app_id}


@router_private.get("/status")
async def get_push_status(req: Request):
    """
    Check if Web Push is configured and available.
    Frontend uses this to show/hide the push toggle in UserMenu.
    """
    env = req.app.state.env

    connector = await env.models.chat_connector.search(
        filter=[
            ("type", "=", "web_push"),
            ("active", "=", True),
        ],
        fields=["id", "client_app_id", "access_token"],
        limit=1,
    )

    if not connector:
        return {"available": False}

    c = connector[0]
    configured = bool(c.client_app_id and c.access_token)

    return {"available": configured}
