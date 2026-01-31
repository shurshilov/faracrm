# Copyright 2025 FARA CRM
# Attachments module - Folder cache model

import logging
from typing import TYPE_CHECKING, Optional, Tuple

from backend.base.system.dotorm.dotorm.components.filter_parser import (
    FilterExpression,
)
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from .attachments_route import AttachmentRoute

logger = logging.getLogger(__name__)


class AttachmentCache(DotModel):
    """
    Кеш folder IDs для маршрутов вложений.

    Преимущества отдельной таблицы над JSON полем:
    - Атомарные UPSERT операции (нет race condition)
    - Индексированный поиск по (route_id, res_model)
    - Независимые строки, нет блокировки всего route
    - Простая инвалидация (DELETE одной строки)
    """

    __table__ = "attachments_cache"

    id: int = Integer(primary_key=True)

    route_id: "AttachmentRoute" = Many2one(
        relation_table=lambda: env.models.attachment_route,
        string="Route",
        required=True,
    )

    res_model: str = Char(
        string="Model",
        required=True,
        help="Model name or '_default' for specific routes",
    )

    folder_id: str = Char(
        string="Folder ID",
        required=True,
        help="Cloud folder ID",
    )

    folder_name: str | None = Char(
        string="Folder Name",
        help="Cached folder name",
    )

    # ========================================================================
    # Cache operations
    # ========================================================================

    @classmethod
    async def get_folder(
        cls,
        route_id: int,
        res_model: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Получить folder ID из кеша.

        Args:
            route_id: ID маршрута
            res_model: Модель или '_default'

        Returns:
            Tuple (folder_id, folder_name) или (None, None)
        """
        cached = await cls.search(
            filter=[
                ("route_id", "=", route_id),
                ("res_model", "=", res_model),
            ],
            limit=1,
            fields=["folder_id", "folder_name"],
        )

        if cached:
            return cached[0].folder_id, cached[0].folder_name
        return None, None

    @classmethod
    async def set_folder(
        cls,
        route_id: int,
        res_model: str,
        folder_id: str,
        folder_name: str | None = None,
    ) -> None:
        """
        Сохранить folder ID в кеш (UPSERT).

        Args:
            route_id: ID маршрута
            res_model: Модель или '_default'
            folder_id: ID папки в облаке
            folder_name: Имя папки
        """
        existing = await cls.search(
            filter=[
                ("route_id", "=", route_id),
                ("res_model", "=", res_model),
            ],
            limit=1,
        )

        if existing:
            update_data = cls()
            update_data.folder_id = folder_id
            update_data.folder_name = folder_name
            await existing[0].update(update_data)
        else:
            new_cache = cls()
            new_cache.route_id = env.models.attachment_route(id=route_id)
            new_cache.res_model = res_model
            new_cache.folder_id = folder_id
            new_cache.folder_name = folder_name
            await cls.create(new_cache)

    @classmethod
    async def delete_folder(
        cls,
        route_id: int,
        res_model: str | None = None,
    ) -> None:
        """
        Удалить записи из кеша.

        Args:
            route_id: ID маршрута
            res_model: Модель (если None - удаляет все для route)
        """
        filter_cond: FilterExpression = [("route_id", "=", route_id)]
        if res_model:
            filter_cond.append(("res_model", "=", res_model))

        cached = await cls.search(filter=filter_cond)
        for cache in cached:
            await cache.delete()

    @classmethod
    async def clear_route_cache(cls, route_id: int) -> None:
        """Очистить весь кеш для маршрута."""
        await cls.delete_folder(route_id)

    @classmethod
    async def clear_storage_cache(cls, storage_id: int) -> None:
        """Очистить кеш для всех маршрутов хранилища."""
        from .attachments_route import AttachmentRoute

        routes = await AttachmentRoute.search(
            filter=[("storage_id", "=", storage_id)],
            fields=["id"],
        )

        for route in routes:
            await cls.clear_route_cache(route.id)
