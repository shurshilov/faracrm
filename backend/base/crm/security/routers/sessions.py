import os
from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.base.crm.auth_token.app import AuthTokenApp, COOKIE_TOKEN_NAME

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from ..models.sessions import Session


router_private = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


class TerminateAllResponse(BaseModel):
    terminated_count: int
    message: str


@router_private.post("/logout")
async def logout(req: Request):
    """Завершить текущую сессию и удалить cookie token."""
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session

    # Деактивируем сессию в БД
    session = env.models.session._get_db_session()
    await session.execute(
        "UPDATE sessions SET active = false WHERE id = %s",
        [auth_session.id],
    )

    # Удаляем cookie token
    response = JSONResponse(content={"success": True})
    response.delete_cookie(
        key=COOKIE_TOKEN_NAME,
        path="/",
        secure=os.getenv("COOKIE_SECURE", "false").lower() != "false",
        samesite="lax",
    )
    return response


@router_private.post("/terminate_all", response_model=TerminateAllResponse)
async def terminate_all_sessions(req: Request, exclude_current: bool = True):
    """
    Завершить все активные сессии текущего пользователя.

    Args:
        exclude_current: Если True, текущая сессия не будет завершена
    """
    env: "Environment" = req.app.state.env

    # Получаем текущий токен из заголовка
    current_token = None
    if exclude_current:
        current_token = req.headers.get("Authorization", "").replace(
            "Bearer ", ""
        )

        # user_id уже есть в сессии (добавлен в session_check)
    auth_session: "Session" = req.state.session
    user_id = auth_session.user_id.id

    async with env.apps.db.get_transaction():
        user = await env.models.user.get_or_none(id=user_id)

        if not user:
            return TerminateAllResponse(
                terminated_count=0, message="User not found"
            )

        terminated_count = await user.terminate_sessions(
            exclude_token=current_token,
        )

        return TerminateAllResponse(
            terminated_count=terminated_count,
            message=f"Successfully terminated {terminated_count} session(s)",
        )
