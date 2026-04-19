from enum import Enum
from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from backend.base.crm.auth_token.app import AuthTokenApp

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
async def logout(req: Request, response: Response):
    """Завершить текущую сессию и удалить cookie token."""
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session

    # Деактивируем сессию в БД
    session = env.models.session._get_db_session()
    await session.execute(
        "UPDATE sessions SET active = false WHERE id = %s",
        [auth_session.id],
    )

    if AuthTokenApp.session_cache_enabled:
        await env.models.session.publish_revoked([auth_session.id])

    response.delete_cookie(
        key=env.settings.auth.cookie_name,
        httponly=True,
        path="/",
        secure=env.settings.auth.cookie_secure,
        samesite=env.settings.auth.cookie_samesite,
    )
    return {"success": True}


class TerminationMode(str, Enum):
    # Все, кроме текущей (по умолчанию)
    MY = "MY"
    # Вообще все
    ALL = "ALL"


@router_private.post("/terminate_all", response_model=TerminateAllResponse)
async def terminate_all_sessions(
    req: Request,
    mode: TerminationMode = TerminationMode.MY,
):
    """
    Завершить все активные сессии текущего пользователя.

    Args:
        exclude_current: Если True, текущая сессия не будет завершена
    """
    env: "Environment" = req.app.state.env
    auth_session: "Session" = req.state.session

    async with env.apps.db.get_transaction():
        user = await env.models.user.get_or_none(id=auth_session.user_id.id)
        if not user:
            return TerminateAllResponse(
                terminated_count=0, message="User not found"
            )
        terminated_count = await user.terminate_sessions(auth_session.id, mode)

        return TerminateAllResponse(
            terminated_count=terminated_count,
            message=f"Sessions terminated in mode: {mode.value}",
        )
