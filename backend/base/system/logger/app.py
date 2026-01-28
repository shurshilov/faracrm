import logging
from backend.base.system.core.enviroment import env
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
        await super().startup(app)
        """Старт сервиса"""
        logging.basicConfig(
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
            level=env.settings.logger.log_level,
        )

    async def shutdown(self, app):
        """Отключение сервиса"""
        ...
