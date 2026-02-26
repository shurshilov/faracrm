# Copyright 2025 FARA CRM
# Standalone cron process entry point
"""
Запуск cron worker как отдельного процесса.

Лёгкий startup: env.cron_mode = True пропускает сервисы
с cron_skip=True (auto_crud, chat, docs, сам cron app).
Это предотвращает рекурсию и экономит ~5-7с на старте.
"""

import asyncio
import logging
import sys


def main():
    """Entry point for standalone cron process."""
    logger = logging.getLogger("cron")

    from backend.project_setup import env

    # cron_mode пропускает сервисы с cron_skip=True
    # (auto_crud, chat, docs, cron app) — нет рекурсии, нет лишней работы
    env.cron_mode = True
    from backend.base.system.cron.process import CronProcess
    from backend.main import app, lifespan

    async def run():
        async with lifespan(app):
            logger.info("=" * 50)
            logger.info("FARA CRM - Cron Process")
            logger.info("=" * 50)

            process = CronProcess(env=env)
            await process.run()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
