# Copyright 2025 FARA CRM
# Cron API router - дополнительные эндпоинты
"""
Дополнительные API endpoints для cron задач.
CRUD операции генерируются автоматически через auto_crud.

Эти эндпоинты добавляют специфичную логику:
- POST /cron_job/{id}/run - запустить задачу немедленно
- PATCH /cron_job/{id}/toggle - включить/выключить задачу
"""

from typing import TYPE_CHECKING
from datetime import datetime, timezone
import asyncio

from fastapi import APIRouter, Depends, Request
from starlette.status import HTTP_404_NOT_FOUND

from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.core.exceptions.environment import FaraException

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment


router_private = APIRouter(
    tags=["cron_job"],
    prefix="/cron_job",
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


@router_private.post("/{job_id}/run")
async def run_job_now(req: Request, job_id: int):
    """
    Запустить задачу немедленно.
    """
    env: "Environment" = req.app.state.env

    # Используем worker если запущен
    cron_app = env.apps.cron
    if cron_app.worker:
        return await cron_app.run_job_now(job_id)

    # Fallback: выполняем напрямую
    try:
        job = await env.models.cron_job.get(job_id)
    except Exception:
        raise FaraException(
            {
                "content": "NOT_FOUND",
                "status_code": HTTP_404_NOT_FOUND,
            }
        )

    start_time = datetime.now(timezone.utc)

    await job.update(
        env.models.cron_job(last_status="running", lastcall=start_time)
    )

    try:
        await asyncio.wait_for(
            job.execute(env),
            timeout=job.timeout,
        )

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        await job.update(
            env.models.cron_job(
                last_status="success",
                last_error="",
                last_duration=duration,
                run_count=job.run_count + 1,
                nextcall=job.calculate_next_call(),
            )
        )

        return {"success": True, "status": "success", "duration": duration}

    except asyncio.TimeoutError:
        await job.update(
            env.models.cron_job(
                last_status="error",
                last_error=f"Timeout after {job.timeout} seconds",
                nextcall=job.calculate_next_call(),
            )
        )

        return {
            "success": False,
            "status": "error",
            "error": f"Timeout after {job.timeout} seconds",
        }

    except Exception as e:
        await job.update(
            env.models.cron_job(
                last_status="error",
                last_error=str(e),
                nextcall=job.calculate_next_call(),
            )
        )

        return {"success": False, "status": "error", "error": str(e)}


@router_private.patch("/{job_id}/toggle")
async def toggle_job(req: Request, job_id: int):
    """
    Включить/выключить задачу.
    """
    env: "Environment" = req.app.state.env

    try:
        job = await env.models.cron_job.get(job_id)
    except Exception:
        raise FaraException(
            {
                "content": "NOT_FOUND",
                "status_code": HTTP_404_NOT_FOUND,
            }
        )

    new_active = not job.active
    new_cron = env.models.cron_job(active=new_active)
    if new_active:
        new_cron.nextcall = job.calculate_next_call()

    await job.update(new_cron)

    return {"success": True, "active": new_active}
