# Copyright 2025 FARA CRM
# Cron App - service registration + subprocess spawn
"""
Модуль cron - управление запланированными задачами.

При startup запускает cron как отдельный процесс (subprocess).
pg_advisory_lock гарантирует: из N uvicorn воркеров только один
реально запустит cron, остальные subprocess-ы сразу завершатся.

Настройки в .env:
    CRON__ENABLED=true
    CRON__CHECK_INTERVAL=60
    CRON__MAX_THREADS=2
"""

import asyncio
import logging
import subprocess
import sys
import os
from typing import TYPE_CHECKING

from backend.base.system.core.service import Service
from backend.base.crm.security.acl_post_init_mixin import ACL
from .settings import CronSettings
from .models.cron_job import CronJob

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


TEST_CREATE_USER_CODE = """
# Создаём тестового пользователя
user=env.models.user(
    name=f"test_cron",
    login=f"cron@test.local")
user_id = await env.models.user.create(user)

result = {
    "action": "created",
    "user_id": user_id,
    "username": user.name,
    "login": user.login,
}
"""

# Интервал проверки жизни subprocess (секунды)
WATCHDOG_INTERVAL = 10


class CronApp(Service):
    """
    Сервис cron.
    Запускает cron worker как отдельный subprocess при startup.
    Watchdog перезапускает subprocess если он упал.
    Advisory lock гарантирует единственный активный инстанс.
    """

    info = {
        "name": "Cron",
        "summary": "Scheduled tasks management",
        "author": "FARA ERP",
        "category": "System",
        "version": "2.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["security", "db"],
        "service": True,
        "post_init": True,
        "sequence": 100,
    }

    BASE_USER_ACL = {
        "cron_job": ACL.READ_ONLY,
    }

    def __init__(self):
        super().__init__()
        self.settings = CronSettings()
        self._cron_process: subprocess.Popen | None = None
        self._watchdog_task: asyncio.Task | None = None
        self._stopping = False

    def _spawn_cron(self) -> subprocess.Popen:
        """Запускает cron subprocess."""
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from backend.cron_main import main; main()",
            ],
            cwd=os.getcwd(),
        )
        logger.info(f"Cron subprocess spawned (PID={proc.pid})")
        return proc

    async def _watchdog(self):
        """
        Следит за cron subprocess.
        Если процесс упал — перезапускает.
        """
        while not self._stopping:
            await asyncio.sleep(WATCHDOG_INTERVAL)

            if self._stopping:
                break

            if self._cron_process and self._cron_process.poll() is not None:
                exit_code = self._cron_process.returncode
                # exit_code 0 = нормальное завершение (advisory lock занят)
                if exit_code != 0:
                    logger.warning(
                        f"Cron subprocess exited with code {exit_code}, "
                        f"restarting..."
                    )
                    self._cron_process = self._spawn_cron()
                else:
                    logger.debug(
                        "Cron subprocess exited normally (lock held by another)"
                    )

    async def startup(self, app: "FastAPI"):
        """
        Запускает cron worker как subprocess.

        Если CRON__ENABLED=false (ставится в cron_main.py),
        startup пропускается — нет рекурсии.
        """
        if not self.settings.enabled:
            logger.info("Cron disabled by settings")
            return

        logger.info("Spawning cron subprocess...")

        self._cron_process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from backend.cron_main import main; main()",
            ],
            cwd=os.getcwd(),
            # Не передаём CRON__ENABLED — cron_main сам поставит false
            # чтобы не отравлять env родительского процесса
        )

        logger.info(f"Cron subprocess spawned (PID={self._cron_process.pid})")

    async def shutdown(self, app: "FastAPI"):
        """Останавливает cron subprocess."""
        if self._cron_process and self._cron_process.poll() is None:
            logger.info(
                f"Terminating cron subprocess (PID={self._cron_process.pid})"
            )
            self._cron_process.terminate()
            try:
                self._cron_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Cron subprocess did not stop, killing...")
                self._cron_process.kill()
                self._cron_process.wait()
            logger.info("Cron subprocess stopped")

    async def post_init(self, app: "FastAPI"):
        """Создание тестовой cron задачи."""
        await super().post_init(app)
        env = app.state.env

        await CronJob.create_or_update(
            env=env,
            name="[TEST] Создать тестового пользователя",
            code=TEST_CREATE_USER_CODE,
            interval_number=1,
            interval_type="hours",
            active=False,
            priority=99,
        )

        logger.info("Cron test task created (inactive by default)")
