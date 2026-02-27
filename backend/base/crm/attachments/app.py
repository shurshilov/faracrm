from typing import TYPE_CHECKING

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment


class AttachmentsApp(App):
    """
    Приложение добавляет вложения и файлы
    """

    info = {
        "name": "Attachments",
        "summary": "Module allow work with binary data. Local and remote files.",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "attachment": ACL.FULL,
        "attachment_storage": ACL.FULL,
        "attachment_route": ACL.FULL,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        await self._init_system_settings(env)
        await self._init_default_storage(env)
        await self._init_default_routes(env)

    async def _init_system_settings(self, env: "Environment"):
        """Создаёт настройки по умолчанию для модуля attachments."""
        import os

        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": "attachments.filestore_path",
                    "value": {"value": os.path.join(os.getcwd(), "filestore")},
                    "description": "Путь к локальному хранилищу файлов",
                    "module": "attachments",
                    "is_system": False,
                    "cache_ttl": -1,
                },
            ]
        )

    async def _init_default_storage(self, env: "Environment"):
        """Создаёт дефолтное хранилище типа file (id=1)."""
        storage = await env.models.attachment_storage.search(
            filter=[("id", "=", 1)], limit=1
        )
        if not storage:
            from backend.base.crm.attachments.models.attachments_storage import (
                AttachmentStorage,
            )

            await env.models.attachment_storage.create(
                payload=AttachmentStorage(
                    name="Local File Storage",
                    type="file",
                    active=True,
                ),
            )

    async def _init_default_routes(self, env: "Environment"):
        """Создаёт дефолтные маршруты для всех хранилищ."""
        from backend.base.crm.attachments.models.attachments_route import (
            AttachmentRoute,
        )

        storages = await env.models.attachment_storage.search(filter=[])
        for storage in storages:
            await AttachmentRoute.ensure_default_route_for_storage(storage.id)
