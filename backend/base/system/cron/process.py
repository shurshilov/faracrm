# Copyright 2025 FARA CRM
# Cron Process - standalone process, isolated from HTTP workers
"""
Отдельный процесс для выполнения cron задач.

Предполагает что сервисы (DB пулы, модели) уже инициализированы
через lifespan в cron_main.py.

Архитектура:
    1. pg_advisory_lock — гарантия одного инстанса
    2. Polling loop: каждые N секунд проверяет задачи
    3. Атомарный захват через SELECT FOR UPDATE SKIP LOCKED
    4. Graceful shutdown
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import asyncpg

from .locking import try_acquire_cron_lock, release_cron_lock
from .models.cron_job import CronJob
from .settings import CronSettings

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)


class CronProcess:
    """
    Standalone cron process.

    Сервисы (DB, модели) инициализируются снаружи через lifespan.
    CronProcess только захватывает lock и выполняет задачи.
    """

    def __init__(self, env: "Environment"):
        self.env = env
        self.settings = CronSettings()
        self.pool: asyncpg.Pool
        self._running = False

    async def run(self) -> None:
        """Главный entry point."""
        if not self.settings.enabled:
            logger.info("Cron disabled by settings")
            return

        # Получаем пул из уже инициализированных сервисов
        self.pool = self._find_pool()
        if not self.pool:
            logger.error("Database pool not found. Are services initialized?")
            return

        # Захватываем advisory lock
        locked = await try_acquire_cron_lock(self.pool)
        if not locked:
            logger.warning("Another cron process holds the lock. Exiting.")
            return

        logger.info(
            "Cron process started (PID=%s, interval=%ss, max_workers=%s)",
            os.getpid(),
            self.settings.check_interval,
            self.settings.max_threads,
        )

        self._running = True

        # Обработка сигналов (Unix only)
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._handle_signal)

        try:
            await self._main_loop()
        except asyncio.CancelledError:
            pass
        finally:
            await self._shutdown()

    def _find_pool(self) -> "asyncpg.Pool | None":
        """Находит asyncpg Pool из инициализированных сервисов."""
        for svc in self.env.services_before:
            pool = getattr(svc, "fara", None)
            if isinstance(pool, asyncpg.Pool):
                return pool
        return None

    def _handle_signal(self) -> None:
        logger.info("Received shutdown signal")
        self._running = False

    async def _main_loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.exception("Error in cron tick")

            try:
                await asyncio.wait_for(
                    self._wait_shutdown(),
                    timeout=self.settings.check_interval,
                )
                break
            except asyncio.TimeoutError:
                pass

    async def _wait_shutdown(self) -> None:
        while self._running:
            await asyncio.sleep(0.5)

    async def _tick(self) -> None:
        await self._write_heartbeat()

        claimed = await CronJob.claim_next_jobs(
            self.pool,
            limit=self.settings.max_threads,
        )

        if not claimed:
            return

        tasks = [self._execute_job(job_data) for job_data in claimed]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_job(self, job_data: dict) -> None:
        job_id = job_data["id"]
        job_name = job_data["name"]

        logger.info("Executing: %s (id=%s)", job_name, job_id)
        start = datetime.now(timezone.utc)

        try:
            job = CronJob(
                **{
                    k: v
                    for k, v in job_data.items()
                    if hasattr(CronJob, k) and k != "id"
                }
            )
            job.id = job_id

            timeout = job_data.get("timeout", 300)
            await asyncio.wait_for(
                job.execute(self.env),
                timeout=timeout,
            )

            duration = (datetime.now(timezone.utc) - start).total_seconds()
            run_count = (job_data.get("run_count") or 0) + 1
            numbercall = job_data.get("numbercall", -1)
            deactivate = numbercall != -1 and run_count >= numbercall

            await CronJob.complete_job(
                self.pool,
                job_id=job_id,
                status="success",
                duration=duration,
                run_count=run_count,
                next_call=job.calculate_next_call(),
                deactivate=deactivate,
            )

            logger.info("Completed: %s (%.2fs)", job_name, duration)
            if deactivate:
                logger.info("Deactivated: %s (reached run limit)", job_name)

        except asyncio.TimeoutError:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            await CronJob.complete_job(
                self.pool,
                job_id=job_id,
                status="error",
                error=f"Timeout after {job_data.get('timeout', 300)}s",
                duration=duration,
                run_count=job_data.get("run_count") or 0,
                next_call=CronJob(
                    lastcall=start,
                    interval_number=job_data.get("interval_number", 1),
                    interval_type=job_data.get("interval_type", "days"),
                ).calculate_next_call(),
            )
            logger.error("Timeout: %s", job_name)

        except Exception as e:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            await CronJob.complete_job(
                self.pool,
                job_id=job_id,
                status="error",
                error=str(e)[:1000],
                duration=duration,
                run_count=job_data.get("run_count") or 0,
                next_call=CronJob(
                    lastcall=start,
                    interval_number=job_data.get("interval_number", 1),
                    interval_type=job_data.get("interval_type", "days"),
                ).calculate_next_call(),
            )
            logger.exception("Failed: %s", job_name)

    async def _write_heartbeat(self) -> None:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO system_settings (key, value)
                    VALUES ('cron_heartbeat', $1)
                    ON CONFLICT (key) DO UPDATE SET value = $1
                    """,
                    datetime.now(timezone.utc).isoformat(),
                )
        except Exception:
            pass

    async def _shutdown(self) -> None:
        logger.info("Shutting down cron process...")
        if self.pool:
            await release_cron_lock(self.pool)
        logger.info("Cron process stopped")
