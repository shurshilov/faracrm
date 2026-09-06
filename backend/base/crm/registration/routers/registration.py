# Copyright 2025 FARA CRM
# Registration module - публичные ручки регистрации

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.registration.schemas.registration import (
    RegistrationConfirmInput,
    RegistrationStartInput,
)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

# Ручки пишут в БД (заявка, затем пользователь), поэтому не анонимная
# сессия, а системная — как /signin. Защита — код из письма.
router_public = APIRouter(
    tags=["Registration"],
    dependencies=[Depends(AuthTokenApp.use_system_session)],
)


@router_public.post("/registration")
async def registration_start(req: Request, payload: RegistrationStartInput):
    """Создать заявку и отправить код подтверждения выбранным каналом."""
    env: "Environment" = req.app.state.env
    async with env.apps.db.get_transaction():
        registration = await env.models.registration.start(
            name=payload.name,
            login=payload.login,
            password=payload.password,
            channel=payload.channel,
        )
    return {
        "data": {
            "login": registration.login,
            "expires_at": registration.expires_at,
        }
    }


@router_public.post("/registration/confirm")
async def registration_confirm(
    req: Request, payload: RegistrationConfirmInput
):
    """Сверить код и создать пользователя. Дальше фронт делает /signin."""
    env: "Environment" = req.app.state.env
    async with env.apps.db.get_transaction():
        user_id = await env.models.registration.confirm(
            login=payload.login, code=payload.code
        )
    return {"data": {"user_id": user_id}}
