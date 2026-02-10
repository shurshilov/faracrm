"""Auto CRUD service — generates routers from DotModel classes."""

from typing import TYPE_CHECKING
from backend.base.system.core.service import Service
from ..dotorm.dotorm.integrations.pydantic import generate_pydantic_models

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment


class DotormCrudAutoService(Service):
    """
    Сервис который добавляет crud ручки
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
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": [],
        "service": True,
    }

    def __init__(self, default_auto_crud=True) -> None:
        super().__init__()
        self.default_auto_crud = default_auto_crud

    async def create_autocrud(self, app, env: "Environment"):
        "Создание CRUD роутов для таблиц"
        from .crud_routers import CRUDRouterGenerator

        # module = importlib.import_module(
        #     "backend.base.system.core.dotorm_crud_auto.crud_routers"
        # )
        # CRUDRouterGenerator = getattr(module, "CRUDRouterGenerator")

        models = env.models._get_models()
        models_schemas = generate_pydantic_models(models)
        for model in models:
            model.__auto_crud__ = self.default_auto_crud
            model.__schema__ = models_schemas[model.__name__]
            if model.__auto_crud__:
                app.include_router(
                    CRUDRouterGenerator(
                        model,
                        tags=[f"{model.__table__} AUTO CRUD"],
                    )
                )

    async def startup(self, app) -> None:
        """Старт сервиса"""
        await super().startup(app)
        env: "Environment" = app.state.env
        await self.create_autocrud(app, env)

    async def shutdown(self, app):
        """Отключение сервиса."""
