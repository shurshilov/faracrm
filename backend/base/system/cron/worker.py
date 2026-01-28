# Copyright 2025 FARA CRM
# Cron Worker - выполняет запланированные задачи
"""
Cron Worker - выполняет задачи из БД.

Запускается автоматически при старте сервера (если CRON__RUN_ON_STARTUP=true)
или вручную через CLI.

Архитектура:
1. Worker запускается как asyncio task в основном процессе
2. Каждые N секунд проверяет БД на наличие задач
3. Выполняет задачи параллельно (с ограничением max_threads)
4. Обновляет статусы в БД
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Set

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from .models.cron_job import CronJob

logger = logging.getLogger("cron.worker")


class CronWorker:
    """
    Воркер для выполнения cron задач.
    """

    def __init__(
        self,
        env: "Environment",
        check_interval: int = 60,
        max_threads: int = 2,
    ):
        """
        Args:
            env: Environment с доступом к моделям
            check_interval: Интервал проверки новых задач (секунды)
            max_threads: Максимум параллельных задач
        """
        self.env = env
        self.check_interval = check_interval
        self.max_threads = max_threads
        self._running = False
        self._task: asyncio.Task | None = None
        self._current_tasks: Set[asyncio.Task] = set()

    async def start(self):
        """
        Запускает воркер как фоновую задачу.
        """
        if self._running:
            logger.warning("Cron Worker already running")
            return

        logger.info(
            f"Starting Cron Worker (interval={self.check_interval}s, "
            f"max_threads={self.max_threads})"
        )
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """
        Останавливает воркер.
        """
        if not self._running:
            return

        logger.info("Stopping Cron Worker...")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Ждём завершения текущих задач
        if self._current_tasks:
            logger.info(f"Waiting for {len(self._current_tasks)} tasks...")
            await asyncio.gather(*self._current_tasks, return_exceptions=True)

        logger.info("Cron Worker stopped")

    async def _run_loop(self):
        """
        Основной цикл воркера.
        """
        while self._running:
            try:
                await self._check_and_run_jobs()
            except Exception as e:
                logger.exception(f"Error in cron check cycle: {e}")

            # Ждём следующего цикла
            await asyncio.sleep(self.check_interval)

    async def _check_and_run_jobs(self):
        """
        Проверяет и запускает задачи.
        """
        try:
            jobs = await self.env.models.cron_job.get_pending_jobs(self.env)
        except Exception as e:
            logger.error(f"Failed to get pending jobs: {e}")
            return

        if not jobs:
            return

        logger.debug(f"Found {len(jobs)} pending jobs")

        for job in jobs:
            # Проверяем лимит параллельных задач
            if len(self._current_tasks) >= self.max_threads:
                # Ждём завершения хотя бы одной задачи
                done, self._current_tasks = await asyncio.wait(
                    self._current_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )

            # Запускаем задачу
            task = asyncio.create_task(self._execute_job(job))
            self._current_tasks.add(task)
            task.add_done_callback(self._current_tasks.discard)

    async def _execute_job(self, job: "CronJob"):
        """
        Выполняет одну задачу.
        """
        logger.info(f"Executing job: {job.name} (id={job.id})")
        start_time = datetime.now(timezone.utc)

        # Помечаем как выполняющуюся
        job.last_status = "running"
        job.lastcall = start_time
        await job.update()

        try:
            # Выполняем через метод модели
            await asyncio.wait_for(
                job.execute(self.env),
                timeout=job.timeout,
            )

            # Успешное выполнение
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            job.last_status = "success"
            job.last_error = ""
            job.last_duration = duration
            job.run_count += 1
            job.nextcall = job.calculate_next_call()

            logger.info(f"Job {job.name} completed (duration={duration:.2f}s)")

            # Деактивируем если достигнут лимит
            if job.numbercall != -1 and job.run_count >= job.numbercall:
                job.active = False
                logger.info(f"Job {job.name} reached run limit, deactivating")

        except asyncio.TimeoutError:
            job.last_status = "error"
            job.last_error = f"Timeout after {job.timeout} seconds"
            job.nextcall = job.calculate_next_call()
            logger.error(f"Job {job.name} timed out")

        except Exception as e:
            job.last_status = "error"
            job.last_error = str(e)
            job.nextcall = job.calculate_next_call()
            logger.exception(f"Job {job.name} failed: {e}")

        finally:
            await job.update()

    async def run_job_now(self, job_id: int) -> dict:
        """
        Запускает задачу немедленно (для ручного запуска).
        """
        try:
            job = await self.env.models.cron_job.get(job_id)
        except Exception:
            return {"success": False, "error": "Job not found"}

        await self._execute_job(job)

        return {
            "success": job.last_status == "success",
            "status": job.last_status,
            "error": job.last_error,
            "duration": job.last_duration,
        }
