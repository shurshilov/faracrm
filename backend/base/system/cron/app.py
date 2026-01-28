# Copyright 2025 FARA CRM
# Cron App
"""
Модуль cron - управление запланированными задачами.

Аналог ir.cron в Odoo.

Настройки в .env:
    CRON__ENABLED=true
    CRON__CHECK_INTERVAL=60
    CRON__MAX_THREADS=2
    CRON__RUN_ON_STARTUP=true
"""

import logging
from typing import TYPE_CHECKING

from backend.base.system.core.service import Service
from backend.base.crm.security.acl_post_init_mixin import ACL
from .settings import CronSettings
from .worker import CronWorker
from .models.cron_job import CronJob

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("cron")


# Тестовый код для создания пользователя
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


class CronApp(Service):
    """
    Приложение для управления запланированными задачами.
    """

    info = {
        "name": "Cron",
        "summary": "Scheduled tasks management (like Odoo ir.cron)",
        "author": "FARA ERP",
        "category": "System",
        "version": "1.0.0",
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
        self.worker: CronWorker | None = None

    async def startup(self, app: "FastAPI"):
        """Запуск Cron Worker при старте сервера."""
        if not self.settings.enabled:
            logger.info("Cron Worker disabled by settings")
            return

        if not self.settings.run_on_startup:
            logger.info("Cron Worker startup disabled")
            return

        env = app.state.env

        self.worker = CronWorker(
            env=env,
            check_interval=self.settings.check_interval,
            max_threads=self.settings.max_threads,
        )

        await self.worker.start()

    async def shutdown(self, app: "FastAPI"):
        """Остановка Cron Worker."""
        if self.worker:
            await self.worker.stop()

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

    async def run_job_now(self, job_id: int) -> dict:
        """Запустить задачу немедленно."""
        if not self.worker:
            return {"success": False, "error": "Worker not running"}
        return await self.worker.run_job_now(job_id)
