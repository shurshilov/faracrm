from fastapi import FastAPI
from typing import TYPE_CHECKING

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL

if TYPE_CHECKING:
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
    }

    async def post_init(self, app: FastAPI):
        await super().post_init(app)
        env: "Environment" = app.state.env

        await self._init_default_storage(env)

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
                ),
            )
