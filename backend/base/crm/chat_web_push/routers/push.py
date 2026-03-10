# Copyright 2025 FARA CRM
# Chat Web Push module - subscription router

import json
import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.base.crm.auth_token.app import AuthTokenApp

logger = logging.getLogger(__name__)

router = APIRouter(
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


@router.post("/subscribe", response_model=PushSubscriptionResponse)
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

    # здесь должен быть лимит 1 и не надо создавать контакт каждый раз иначе их будет слишком много?
    existing = await env.models.contact.search(
        filter=[
            ("user_id", "=", user_id),
            ("contact_type_id", "=", contact_type_id),
            ("active", "=", True),
        ],
    )

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
            continue

    await env.models.contact.create(
        env.models.contact(
            user_id=auth_session.user_id,
            contact_type_id=contact_type[0],
            name=subscription_json,
            is_primary=len(existing) == 0,
        )
    )

    logger.info(
        "[web_push] Created subscription for user %s (total: %d)",
        user_id,
        len(existing) + 1,
    )
    return PushSubscriptionResponse(
        success=True, message="Subscribed successfully"
    )


@router.post("/unsubscribe", response_model=PushSubscriptionResponse)
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


@router.get("/vapid-key")
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
