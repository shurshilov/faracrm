# Copyright 2025 FARA CRM
# Captcha module - публичная ручка выдачи задачки

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.crm.captcha.image import render_challenge

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

# Без входа: анонимная сессия, а задачку в БД пишет sudo — ровно одна
# операция, больше ручке ничего не разрешено.
router_public = APIRouter(
    tags=["Captcha"],
    dependencies=[Depends(AuthTokenApp.use_anonymous_session)],
)


@router_public.get("/captcha/new")
async def captcha_new(req: Request):
    """Новая задачка: {token, image}. image — PNG data-URI (не текст в DOM)."""
    env: "Environment" = req.app.state.env
    async with env.apps.db.get_transaction():
        token, question = (
            await env.models.captcha_challenge.sudo().new_challenge()
        )
    return {"data": {"token": token, "image": render_challenge(question)}}
