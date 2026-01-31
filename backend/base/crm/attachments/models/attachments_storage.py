# Copyright 2025 FARA CRM
# Attachments module - Storage model
# OPTIMIZED: cascade deactivation of routes, cache clearing

import logging
from typing import TYPE_CHECKING, List, Optional

from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    One2many,
    Selection,
    Boolean,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from .attachments_route import AttachmentRoute

logger = logging.getLogger(__name__)


class AttachmentStorage(DotModel):
    """
    Модель для настройки хранилищ вложений.

    Поддерживает различные типы хранилищ через паттерн Strategy.
    Активным может быть только одно хранилище одновременно.

    Attributes:
        name: Название хранилища
        type: Тип хранилища (file, google, etc.)
        active: Флаг активного хранилища (только одно активно)
    """

    __table__ = "attachments_storage"

    id: int = Integer(primary_key=True)

    name: str = Char(
        string="Name",
        help="Display name of the storage",
    )

    type: str = Selection(
        options=[("file", "FileStore (local)")],
        default="file",
        string="Storage Type",
    )

    active: bool = Boolean(
        default=False,
        string="Active",
        help="Only one storage can be active at a time. Active storage is used for new files.",
    )

    # Sync settings
    enable_realtime: bool = Boolean(
        default=False,
        string="Enable real-time sync",
        help="Automatically sync files to cloud when created",
    )

    enable_one_way_cron: bool = Boolean(
        default=False,
        string="Enable one-way cron sync",
        help="Sync files from local to cloud via scheduled job",
    )

    enable_two_way_cron: bool = Boolean(
        default=False,
        string="Enable two-way cron sync",
        help="Sync files in both directions via scheduled job",
    )

    enable_routes_cron: bool = Boolean(
        default=False,
        string="Enable routes cron sync",
        help="Sync folder structure and names via scheduled job",
    )

    # Action when file not found
    file_missing_cloud: str = Selection(
        options=[
            ("nothing", "Do nothing"),
            ("cloud", "Delete from FARA"),
        ],
        default="nothing",
        string="If file missing in cloud",
        help="Action when file exists in FARA but not in cloud",
    )

    file_missing_local: str = Selection(
        options=[
            ("nothing", "Do nothing"),
            ("cloud", "Import to FARA"),
        ],
        default="nothing",
        string="If file missing in FARA",
        help="Action when file exists in cloud but not in FARA",
    )

    route_ids: list["AttachmentRoute"] = One2many(
        store=False,
        relation_table=lambda: env.models.attachment_route,
        relation_table_field="storage_id",
    )

    # ========================================================================
    # Activation / Deactivation with cascade
    # ========================================================================

    async def activate(self) -> None:
        """Активировать хранилище и все его маршруты."""
        from .attachments_route import AttachmentRoute

        async with env.apps.db.get_transaction():
            self.active = True
            await self.update(self)

            routes = await AttachmentRoute.search(
                filter=[("storage_id", "=", self.id)],
                fields=["id"],
            )
            if routes:
                await AttachmentRoute.update_bulk(
                    [route.id for route in routes],
                    AttachmentRoute(active=True),
                )

            logger.info(
                f"Storage '{self.name}' activated with {len(routes)} routes"
            )

    async def deactivate(self) -> None:
        """Деактивировать хранилище, его маршруты и очистить кеш."""
        from .attachments_route import AttachmentRoute
        from .attachments_cache import AttachmentCache

        async with env.apps.db.get_transaction():
            # Деактивируем routes
            routes = await AttachmentRoute.search(
                filter=[("storage_id", "=", self.id), ("active", "=", True)],
                fields=["id"],
            )
            if routes:
                await AttachmentRoute.update_bulk(
                    [route.id for route in routes],
                    AttachmentRoute(active=False),
                )

            # Очищаем кеш
            await AttachmentCache.clear_storage_cache(self.id)

            # Деактивируем storage
            self.active = False
            await self.update(self)

            logger.info(
                f"Storage '{self.name}' deactivated with {len(routes)} routes"
            )

    # ========================================================================
    # Default storage
    # ========================================================================

    @classmethod
    async def get_active_storage(cls) -> Optional["AttachmentStorage"]:
        result = await cls.search(filter=[("active", "=", True)], limit=1)
        return result[0] if result else None

    @classmethod
    async def get_or_create_default(cls) -> "AttachmentStorage":
        storage = await cls.get_active_storage()
        if storage:
            return storage

        storages = await cls.search(filter=[("type", "=", "file")], limit=1)
        if storages:
            storage = storages[0]
            await storage.activate()
            return storage

        new_storage = cls()
        new_storage.name = "Default FileStore"
        new_storage.type = "file"
        new_storage.active = True

        storage_id = await cls.create(new_storage)
        result = await cls.search(filter=[("id", "=", storage_id)], limit=1)
        return result[0] if result else new_storage

    # ========================================================================
    # Route management
    # ========================================================================

    async def get_routes(self) -> List["AttachmentRoute"]:
        """
        Get all routes for this storage.

        Returns:
            List of routes
        """
        from .attachments_route import AttachmentRoute

        return await AttachmentRoute.search(
            filter=[("storage_id", "=", self.id), ("active", "=", True)],
        )

    # ========================================================================
    # CRUD with cascade activation
    # ========================================================================

    async def update(
        self,
        payload=None,
        fields: list | None = None,
        session=None,
    ) -> None:
        """Update storage with cascade activation/deactivation."""
        # Check if active field is being changed
        if (
            payload
            and payload.active is not None
            and payload.active != self.active
        ):
            if payload.active:
                await self.activate()
            else:
                await self.deactivate()
            # Remove active from payload since activate/deactivate already handled it
            # payload.active = False

        await super().update(payload, fields, session)

    # ========================================================================
    # Sync methods
    # ========================================================================

    @classmethod
    async def start_one_way_sync(cls) -> None:
        logger.info("Starting one-way sync (FARA -> Cloud)")
        storages = await cls.search(
            filter=[("enable_one_way_cron", "=", True), ("active", "=", True)],
        )
        for storage in storages:
            await storage._sync_one_way()

    async def _sync_one_way(self) -> None:
        from .attachments import Attachment

        logger.info(f"One-way sync for storage {self.id}: {self.name}")
        routes = await self.get_routes()

        for route in routes:
            attachment_ids = await route.get_attachments_to_sync(self.id)
            for attach_id in attachment_ids:
                try:
                    attachments = await Attachment.search(
                        filter=[("id", "=", attach_id)],
                        fields=["id", "storage_id", "route_id"],
                        limit=1,
                    )
                    if attachments:
                        attach = attachments[0]
                        update_data = Attachment()
                        update_data.storage_id = self
                        update_data.route_id = route
                        await attach.update(update_data)
                except Exception as e:
                    logger.error(f"Failed to sync attachment {attach_id}: {e}")

    @classmethod
    async def start_two_way_sync(cls) -> None:
        logger.info("Starting two-way sync")
        storages = await cls.search(
            filter=[("enable_two_way_cron", "=", True), ("active", "=", True)],
        )
        for storage in storages:
            await storage._sync_two_way()

    async def _sync_two_way(self) -> None:
        """Sync this storage two-way."""
        from .attachments import Attachment
        from backend.base.crm.attachments.strategies import (
            get_strategy,
            has_strategy,
        )

        logger.info(f"Two-way sync for storage {self.id}: {self.name}")

        if not has_strategy(self.type):
            logger.warning(f"No strategy for storage type {self.type}")
            return

        strategy = get_strategy(self.type)

        # Check if strategy supports listing files
        if not hasattr(strategy, "list_files"):
            logger.debug(f"Strategy {self.type} does not support list_files")
            return

        # Get files from cloud
        try:
            cloud_files = await strategy.list_files(self)
            cloud_file_ids = {f["id"] for f in cloud_files}
        except Exception as e:
            logger.error(f"Failed to list cloud files: {e}")
            return

        # Get files from FARA
        attachments = await Attachment.search(
            filter=[
                ("storage_id", "=", self.id),
                ("storage_file_id", "!=", None),
            ],
        )
        local_file_ids = {
            a.storage_file_id for a in attachments if a.storage_file_id
        }

        # Files in FARA but not in cloud
        missing_in_cloud = local_file_ids - cloud_file_ids
        if missing_in_cloud and self.file_missing_cloud == "cloud":
            logger.info(
                f"Removing {len(missing_in_cloud)} attachments missing from cloud"
            )
            for attach in attachments:
                if attach.storage_file_id in missing_in_cloud:
                    try:
                        await attach.delete()
                    except Exception as e:
                        logger.error(
                            f"Failed to delete attachment {attach.id}: {e}"
                        )

        # Files in cloud but not in FARA
        missing_in_local = cloud_file_ids - local_file_ids
        if missing_in_local and self.file_missing_local == "cloud":
            logger.info(f"Importing {len(missing_in_local)} files from cloud")
            cloud_files_dict = {f["id"]: f for f in cloud_files}
            for file_id in missing_in_local:
                cloud_file = cloud_files_dict.get(file_id)
                if cloud_file:
                    try:
                        await self._import_file_from_cloud(
                            cloud_file, strategy
                        )
                    except Exception as e:
                        logger.error(f"Failed to import file {file_id}: {e}")

    async def _import_file_from_cloud(
        self, cloud_file: dict, strategy
    ) -> None:
        """Import a file from cloud to FARA."""
        from .attachments import Attachment

        # Get metadata from parent folder if available
        metadata = {}
        if hasattr(strategy, "get_file_metadata_from_parent"):
            metadata = await strategy.get_file_metadata_from_parent(
                cloud_file, self
            )

        # Create attachment record
        attach = Attachment()
        attach.name = cloud_file.get("name", "Unknown")
        attach.storage_id = self
        attach.storage_file_id = cloud_file.get("id")
        attach.storage_file_url = cloud_file.get(
            "webViewLink"
        ) or cloud_file.get("link")
        attach.storage_parent_id = (cloud_file.get("parents") or [None])[0]
        attach.res_model = metadata.get("res_model")
        attach.res_id = (
            int(metadata.get("res_id")) if metadata.get("res_id") else None
        )
        attach.route_id = (
            int(metadata.get("route_id")) if metadata.get("route_id") else None
        )

        await Attachment.create(attach)
        logger.debug(f"Imported file {cloud_file.get('id')} from cloud")

    @classmethod
    async def start_routes_sync(cls) -> None:
        """
        Routes sync: Update folder names and move files between routes.
        """
        logger.info("Starting routes sync")
        storages = await cls.search(
            filter=[("enable_routes_cron", "=", True), ("active", "=", True)],
        )
        for storage in storages:
            await storage._sync_routes()

    async def _sync_routes(self) -> None:
        """Sync routes for this storage."""
        logger.info(f"Routes sync for storage {self.id}: {self.name}")

        # Get all routes for this storage
        routes = await self.get_routes()

        for route in routes:
            # Sync root folder name if changed
            await route.sync_root_folder_name(self)

            # TODO: Sync record folder names
            # TODO: Move files between routes if route filter changed
