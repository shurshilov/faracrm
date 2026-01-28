import logging

from .app import App

log: logging.Logger = logging.getLogger(__package__)


class Service(App):
    """
    Класс сервиса, это приложения у которых есть
    действия при старте и завершении программы.
    Паттерн синглтон, каждый сервис может
    быть создан только один раз
    """

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance

    # @abstractmethod
    async def startup(self, app): ...

    # @abstractmethod
    async def shutdown(self, app): ...

    async def startup_depends(self, app):
        if self.info.get("depends"):
            for depend in self.info.get("depends"):
                service = getattr(app.state.env.apps, depend, None)
                if isinstance(service, Service):
                    if service and service.info.get("service"):
                        await service.startup_depends(app)
        log.info(f"Startup service: {self.info.get("name")}")
        await self.startup(app)
