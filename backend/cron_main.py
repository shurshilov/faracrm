# Copyright 2025 FARA CRM
# Standalone cron process entry point
"""
Запуск cron worker как отдельного процесса.

Использует тот же FastAPI app + lifespan для полной
инициализации сервисов (DB пулы, модели).

Трюк: ставим CRON__ENABLED=false перед lifespan,
чтобы CronApp.startup() не спавнил subprocess рекурсивно.
После lifespan восстанавливаем и запускаем process.
"""

import asyncio
import logging
import os
import sys


def main():
    logger = logging.getLogger("cron")

    # Отключаем cron spawn внутри lifespan (иначе рекурсия)
    os.environ["CRON__ENABLED"] = "false"

    from backend.main import app, lifespan
    from backend.project_setup import env
    from backend.base.system.cron.process import CronProcess

    async def run():
        async with lifespan(app):
            logger.info("=" * 50)
            logger.info("FARA CRM - Cron Process")
            logger.info("=" * 50)

            # Восстанавливаем CRON__ENABLED
            os.environ["CRON__ENABLED"] = "true"

            process = CronProcess(env=env)
            await process.run()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
