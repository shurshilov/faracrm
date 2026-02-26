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

        # Применяем FaraFormatter ко всем fara-логгерам.
        # Если логгер ещё не имеет handler (yaml не подхватился) — создаём.
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

            if lgr.handlers:
                # yaml подхватился — просто подменяем formatter
                for handler in lgr.handlers:
                    handler.setFormatter(formatter)
            else:
                # handler нет — создаём (cron subprocess или yaml не загрузился)
                handler = logging.StreamHandler()
                handler.setFormatter(formatter)
                lgr.addHandler(handler)
                lgr.propagate = False

        # Uvicorn — цветные логи как в стандартном FastAPI.
        # Handler'ы могут не существовать при startup (uvicorn создаёт позже).
        # Ставим свои handler'ы сразу и блокируем propagate.
        try:
            from uvicorn.logging import DefaultFormatter, AccessFormatter

            # uvicorn.error — серверные события (startup, WebSocket, shutdown)
            error_fmt = DefaultFormatter(
                "%(levelprefix)s %(message)s",
                use_colors=True,
            )
            for lgr_name in ("uvicorn", "uvicorn.error"):
                lgr = logging.getLogger(lgr_name)
                lgr.handlers.clear()
                h = logging.StreamHandler()
                h.setFormatter(error_fmt)
                lgr.addHandler(h)
                lgr.propagate = False

            # uvicorn.access — HTTP запросы с цветными статус кодами
            access_fmt = AccessFormatter(
                '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                use_colors=True,
            )
            access_lgr = logging.getLogger("uvicorn.access")
            access_lgr.handlers.clear()
            h = logging.StreamHandler()
            h.setFormatter(access_fmt)
            access_lgr.addHandler(h)
            access_lgr.propagate = False

        except ImportError:
            pass  # uvicorn не установлен (cron subprocess)

    async def shutdown(self, app):
        """Отключение сервиса."""
