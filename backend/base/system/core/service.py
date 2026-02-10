import logging

from .app import App

log: logging.Logger = logging.getLogger(__package__)


class Service(App):
    """
    Класс сервиса — приложения с действиями при старте и завершении.

    Паттерн синглтон: каждый сервис может быть создан только один раз.
    """

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance

    async def startup(self, app):
        """Старт сервиса (override в наследниках)."""

    async def shutdown(self, app):
        """Остановка сервиса (override в наследниках)."""

    async def startup_depends(self, app):
        """Запуск сервиса с предварительным запуском зависимостей."""
        if self.info.get("depends"):
            for depend in self.info.get("depends"):
                service = getattr(app.state.env.apps, depend, None)
                if isinstance(service, Service):
                    if service and service.info.get("service"):
                        await service.startup_depends(app)
        log.info("Startup service: %s", self.info.get("name"))
        await self.startup(app)
