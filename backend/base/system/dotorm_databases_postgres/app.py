"""PostgreSQL database service — pool management and model binding."""

from typing import TYPE_CHECKING

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.base.system.core.service import Service
from ..dotorm.dotorm.access import AccessDenied
from ..dotorm.dotorm.builder.builder import Builder
from ..dotorm.dotorm.components.dialect import POSTGRES
from ..dotorm.dotorm.exceptions import RecordNotFound
from backend.base.system.dotorm.dotorm.databases.postgres.transaction import (
    ContainerTransaction,
)
from backend.base.system.dotorm.dotorm.databases.postgres.session import (
    NoTransactionSession,
)
from backend.base.system.dotorm.dotorm.databases.postgres.pool import (
    ContainerPostgres,
)
from backend.base.system.dotorm.dotorm.databases.abstract.types import (
    ContainerSettings,
    PostgresPoolSettings,
)

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Settings, Models


class DotormDatabasesPostgresService(Service):
    """
    Паттерн фасад, данный класс обьединяет пул и транзакции.
    """

    info = {
        "name": "Dotorm databases postgres",
        "summary": "Module allow work with databases postgres sql",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": [],
        "service_start_before": True,
        "sequence": 2,
        "service": True,
    }

    # TODO: dynamyc
    fara: asyncpg.Pool

    def __init__(self, default_database="fara") -> None:
        super().__init__()
        self.default_database = default_database

    async def create_pools(
        self,
        settings: "Settings",
        models: "Models",
    ):
        models_list = models._get_models()
        # установить базу данных по умолчанию
        for model in models_list:
            model.__database__ = self.default_database

        if settings.dotorm_databases_postgres:

            for (
                db_name,
                db_config,
            ) in settings.dotorm_databases_postgres.items():
                pool_settings = PostgresPoolSettings(
                    host=db_config.host,
                    port=db_config.port,
                    user=db_config.user,
                    password=db_config.password,
                    database=db_config.database,
                )
                container_settings = ContainerSettings(
                    reconnect_timeout=10, driver="asyncpg"
                )
                container = ContainerPostgres(
                    pool_settings, container_settings
                )

                try:
                    await container.create_pool()
                    assert isinstance(container.pool, asyncpg.Pool)
                    setattr(self, db_name, container.pool)
                except (
                    asyncpg.InvalidCatalogNameError,
                    asyncpg.ConnectionDoesNotExistError,
                ):
                    # База данных не создана, создать ее
                    if db_config.sync_db:
                        await container.create_database()
                        # Создать пулл подключений к созданной новой базе данных
                        pool = await container.create_pool()
                        assert isinstance(pool, asyncpg.Pool)
                        setattr(self, db_name, pool)

                if db_config.sync_db:
                    # создать или обновить таблицы, в текущей БД
                    await container.create_and_update_tables(
                        [
                            model
                            for model in models_list
                            if model.__database__ == pool_settings.database
                        ]
                    )

            # TODO:
            # привязываем пулы к моделям
            # скорей всего надо присвоить не пул а сразу классы
            # transacton и no_transaction
            for model in models_list:
                # присвоить пул в соответствии с атрибутом класса __database__
                model._pool = getattr(self, model.__database__)
                model._dialect = POSTGRES
                model._builder = Builder(
                    table=model.__table__,
                    fields=model.get_fields(),
                    dialect=model._dialect,
                )
                # присвоить класс для сессии без транзакции
                # это необходимо для удобства, чтобы не передавать каждый раз сессию
                # в орм, а чтобы она создавалась по умолчанию с разу в нужном виде
                # (с транзакцией или без) и к нужному пуллу базы данных
                model._no_transaction = (
                    model._dialect.get_no_transaction_session()
                )

    def get_session(self):
        """
        Returns:
            db session from pool without transaction
        """
        db_pool = self.fara
        db_session = NoTransactionSession(db_pool)
        return db_session

    def get_transaction(self):
        """
        Returns:
            db session from pool with transaction, as context manager
        """
        db_pool = self.fara
        ContainerTransaction.default_pool = db_pool
        db_transaction = ContainerTransaction()
        return db_transaction

    def handler_errors(self, app_server: FastAPI):
        """Регистрирует глобальные обработчики ошибок ORM."""

        async def record_not_found_handler(request: Request, exc: Exception):
            assert isinstance(exc, RecordNotFound)
            return JSONResponse(
                content={
                    "error": "#NOT_FOUND",
                    "message": str(exc),
                    "model": exc.model,
                    "id": exc.id,
                },
                status_code=404,
            )

        async def access_denied_handler(request: Request, exc: Exception):
            assert isinstance(exc, AccessDenied)
            return JSONResponse(
                content={"error": "#ACCESS_DENIED", "message": exc.message},
                status_code=403,
            )

        app_server.add_exception_handler(AccessDenied, access_denied_handler)
        app_server.add_exception_handler(
            RecordNotFound, record_not_found_handler
        )

    async def startup(self, app) -> None:
        """Старт сервиса"""
        await super().startup(app)
        settings: "Settings" = app.state.env.settings
        models: "Models" = app.state.env.models

        # создать пулы соединений к базам данных (в теории их может быть больше одной)
        await self.create_pools(settings, models)
        # сразу присваиваем пул по умолчанию, чтобы не передавать каждый раз
        # несмотря на то что пулов может быть несколько, конкретно в данном проекте
        # подразумевается пул по умолчанию fara как наиболее часто используемый
        NoTransactionSession.default_pool = self.fara

        # Регистрируем глобальные обработчики ошибок
        self.handler_errors(app)

    async def shutdown(self, app):
        """Отключение сервиса"""
        # assert isinstance(self.fara, asyncpg.Pool)
        # await self.fara.close()
        for pool_name in self.__dict__:
            pool = getattr(self, pool_name)
            if isinstance(pool, asyncpg.Pool):
                # await pool.close()
                pool.terminate()
