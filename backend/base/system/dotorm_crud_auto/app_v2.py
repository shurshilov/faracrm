"""
DotORM CRUD Auto Service - автоматическая генерация CRUD роутеров.

Оптимизированная версия с использованием SchemaRegistry:
- Все схемы генерируются за один проход при старте
- Кэширование предотвращает повторную генерацию
- Значительно быстрее старой версии с миксинами
"""

from typing import TYPE_CHECKING
import logging
import time

log = logging.getLogger(__name__)

from backend.base.system.core.service import Service
from .schema_registry import schema_registry

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment


class DotormCrudAutoService(Service):
    """
    Сервис автоматической генерации CRUD роутеров.

    Создаёт роутеры для:
    - GET /{model}/{id} - получить запись
    - POST /{model}/search - поиск записей
    - POST /{model} - создать запись
    - PATCH /{model}/{id} - обновить запись
    - DELETE /{model}/{id} - удалить запись
    """

    info = {
        "name": "Dotorm crud auto",
        "summary": """
        1. Module add CRUD routers for read, create, update, delete, get default values,
        read many2many records, read list record with filter.
        2. Module add pydantic schemas of validation for every router,
        that automate generated from dotorm models""",
        "author": "FARA ERP",
        "category": "Base",
        "version": "2.0.0",  # Новая версия с оптимизацией
        "license": "FARA CRM License v1.0",
        "depends": [],
        "service": True,
    }

    def __init__(self, default_auto_crud: bool = True) -> None:
        super().__init__()
        self.default_auto_crud = default_auto_crud

    async def create_autocrud(self, app, env: "Environment") -> None:
        """Создание CRUD роутов для всех моделей."""
        from .crud_routers_v2 import CRUDRouterGenerator

        start_time = time.perf_counter()

        # Получаем все модели
        models = env.models._get_models()

        # Шаг 1: Генерируем все схемы за один проход
        schema_registry.build_all(models)

        schema_time = time.perf_counter()
        log.info(f"Schemas generated in {schema_time - start_time:.3f}s")

        # Шаг 2: Создаём роутеры
        for model in models:
            model.__auto_crud__ = self.default_auto_crud
            model.__schema__ = schema_registry.get_base_schema(model)

            if model.__auto_crud__:
                router = CRUDRouterGenerator(
                    model,
                    schema_registry=schema_registry,
                    tags=[f"{model.__table__} AUTO CRUD"],
                )
                app.include_router(router)

        end_time = time.perf_counter()
        log.info(f"Routers created in {end_time - schema_time:.3f}s")
        log.info(
            f"Total: {end_time - start_time:.3f}s for {len(models)} models"
        )

    async def startup(self, app) -> None:
        """Старт сервиса."""
        await super().startup(app)
        env: "Environment" = app.state.env
        await self.create_autocrud(app, env)

    async def shutdown(self, app) -> None:
        """Отключение сервиса."""
