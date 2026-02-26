"""Logger service — configures colored log formatting."""

import logging
from backend.base.system.core.service import Service

LOG = logging.getLogger(__package__)


class LoggerService(Service):
    """
    Сервис который добавляет оффлайн документацию
    """

    info = {
        "name": "App logger",
        "summary": "This app congigurate logger in python",
        "author": "Artem Shurshilov",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": [],
        "service": True,
        "service_start_before": True,
        "sequence": 1,
    }

    async def startup(self, app):
        """Старт сервиса — настройка форматирования логов."""
        await super().startup(app)
        from backend.base.system.logger.colored import FaraFormatter

        formatter = FaraFormatter(
            fmt="%(asctime)s  %(levelname)-8s  %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )

        # Применяем FaraFormatter только к fara-логгерам.
        # propagate=False — изолируем от uvicorn handlers,
        # чтобы не ломать нативные цветные логи uvicorn/FastAPI.
        for logger_name in (
            "backend.base.crm",
            "backend.base.system",
            "cron",
            "cron.worker",
            "cron.process",
            "cron.jobs",
        ):
            lgr = logging.getLogger(logger_name)
            lgr.setLevel(logging.INFO)
            lgr.propagate = False

            if lgr.handlers:
                for handler in lgr.handlers:
                    handler.setFormatter(formatter)
            else:
                handler = logging.StreamHandler()
                handler.setFormatter(formatter)
                lgr.addHandler(handler)

    async def shutdown(self, app):
        """Отключение сервиса."""
