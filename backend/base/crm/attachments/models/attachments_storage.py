# Copyright 2025 FARA CRM
# Attachments module - Storage model

from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Selection,
    Boolean,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env


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
        options=[
            ("file", "FileStore (local)"),
            # Дополнительные типы добавляются через @extend в модулях:
            # ("google", "Google Drive") - добавляется модулем attachments_google
            # ("microsoft", "Microsoft OneDrive") - добавляется модулем attachments_microsoft
            # и т.д.
        ],
        default="file",
        string="Storage Type",
        help="Type of storage backend. Additional types can be added by installing extension modules.",
    )

    active: bool = Boolean(
        default=False,
        string="Active",
        help="Only one storage can be active at a time. Active storage is used for new files.",
    )

    async def activate_single(self) -> None:
        """
        Активировать это хранилище и деактивировать остальные.

        Гарантирует, что только одно хранилище активно одновременно.
        """

        async with env.apps.db.get_transaction():
            # Деактивируем все хранилища
            all_storages = await env.models.attachment_storage.search(
                filter=[("active", "=", True)],
                fields=["id", "active"],
            )
            if all_storages:
                await env.models.attachment_storage.update_bulk(
                    [storage.id for storage in all_storages],
                    env.models.attachment_storage(active=False),
                )

            # Активируем текущее
            self.active = True
            await self.update(self)

    async def deactivate(self) -> None:
        """Деактивировать хранилище."""
        self.active = False
        await self.update(self)

    @classmethod
    async def get_active_storage(cls):
        """
        Получить активное хранилище.

        Returns:
            Активное хранилище или None если ни одно не активно
        """

        result = await env.models.attachment_storage.search(
            filter=[("active", "=", True)],
            fields=["id"],
            limit=1,
        )
        if result:
            return env.models.attachment_storage(id=result[0].id)
        else:
            return None

    @classmethod
    async def get_or_create_default(cls) -> "AttachmentStorage":
        """
        Получить активное хранилище или создать FileStore по умолчанию.

        Returns:
            Активное хранилище
        """

        # Ищем активное
        storage = await cls.get_active_storage()
        if storage:
            return storage

        # Ищем любой filestore
        storages = await env.models.attachment_storage.search(
            filter=[("type", "=", "file")],
            fields=["id"],
            limit=1,
        )

        if storages:
            storage = storages[0]
            await storage.activate_single()
            return storage

        # Создаем новый filestore
        new_storage = env.models.attachment_storage()
        new_storage.name = "Default FileStore"
        new_storage.type = "file"
        new_storage.active = True

        storage_id = await env.models.attachment_storage.create(new_storage)
        result = await env.models.attachment_storage.search(
            filter=[("id", "=", storage_id)],
            fields=["id"],
            limit=1,
        )
        return result[0] if result else new_storage
