import base64
import os
from typing import Self
from ....system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Binary,
    Char,
    Integer,
    Boolean,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from .attachments_storage import AttachmentStorage
from backend.base.system.core.enviroment import env


class Attachment(DotModel):
    __table__ = "attachments"

    @classmethod
    async def _get_default_storage_id(cls):
        storage_id = await env.models.attachment_storage.search(
            limit=1,
            fields=["id", "name", "type"],
        )
        if len(storage_id):
            return storage_id[0]
        else:
            return None

    id: int = Integer(primary_key=True)
    name: str = Char()
    res_model: str | None = Char(
        string="Resource Model",
    )
    res_field: str | None = Char(
        string="Resource Field",
    )
    res_id: int | None = Integer(string="Resource ID")
    # company_id = Many2one(string='Company', relation_table=Company)
    public: bool = Boolean(string="Is public document")
    folder: bool = Boolean(string="Is folder")
    access_token: str | None = Char(
        string="Access Token",
    )
    size: int = Integer(
        string="File Size",
    )
    checksum: str | None = Char(string="Checksum/SHA1", max_length=40)
    mimetype: str | None = Char(
        string="Mime Type",
    )
    storage_id: AttachmentStorage | None = Many2one(
        relation_table=AttachmentStorage,
        string="Cloud storage",
        # default=_get_default_storage_id,
    )

    # route_id = fields.Many2one(
    #     comodel_name="cloud.storage.route",
    #     string="Cloud storage route",
    #     copy=False,
    #     # tracking=True,
    # )

    storage_file_id: str | None = Char(
        string="Storage file ID",
        help="""If cloud (Google...) is cloud file id""",
    )

    storage_parent_id: str | None = Char(
        string="Storage file parent ID",
    )

    storage_parent_name: str | None = Char(
        string="Storage file parent Name",
    )

    storage_file_url: str | None = Char(
        string="Storage file url",
        help="Usually use for preview and edit file.",
    )

    is_voice: bool = Boolean(
        default=False,
        string="Is voice message",
        help="True if attachment is a voice recording from chat",
    )

    content: bytes | None = Binary(
        string="Binary content of data",
        store=False,
        help="Compute field, that not stored in db",
    )

    async def read_content(self) -> bytes | None:
        """
        Прочитать содержимое файла.
        Возвращает bytes или None если файл не найден.
        """
        if self.content:
            return self.content

        if self.storage_file_url and os.path.exists(self.storage_file_url):
            if self.storage_id and self.storage_id.type == "file":
                try:
                    with open(self.storage_file_url, "rb") as f:
                        self.content = f.read()
                        return self.content
                except IOError:
                    return None

        return None

    async def update(self, payload: Self | None = None, fields=None):
        if not fields:
            fields = []
        if payload and self.storage_id and payload.content:
            async with env.apps.db.get_transaction():
                # TODO: работать со строкой type safing
                content_bytes = base64.b64decode(payload.content)
                # в базу контент не сохраняем
                payload.content = None
                await super().update(payload)

                # TODO: передеалать на pattern strategy self.storage_id.create_file
                if self.storage_id.type == "file":
                    filestore_path = env.settings.attachments.filestore_path
                    payload.storage_file_url = f"{filestore_path}\\{payload.res_model}\\{payload.res_id}\\{payload.name}"
                    if not os.path.exists(payload.storage_file_url):
                        try:
                            os.makedirs(
                                os.path.dirname(payload.storage_file_url),
                                exist_ok=True,
                            )
                            with open(payload.storage_file_url, "wb") as fp:
                                fp.write(content_bytes)
                        except IOError:
                            print("ERROR CREATE ATTACHMENT FILE")
        else:
            await super().update(payload, fields)

    @hybridmethod
    async def create(self, payload):
        storage_id = await self._get_default_storage_id()
        if payload and storage_id and payload.content:
            async with env.apps.db.get_transaction():
                content_bytes = base64.b64decode(payload.content)
                # в базу контент не сохраняем
                payload.content = None
                payload.storage_id = storage_id
                filestore_path = env.settings.attachments.filestore_path
                payload.storage_file_url = f"{filestore_path}\\{payload.res_model}\\{payload.res_id}\\{payload.name}"
                id = await super().create(payload)

                # TODO: передеалать на pattern strategy self.storage_id.create_file
                if storage_id.type == "file":
                    if not os.path.exists(payload.storage_file_url):
                        try:
                            os.makedirs(
                                os.path.dirname(payload.storage_file_url),
                                exist_ok=True,
                            )
                            with open(payload.storage_file_url, "wb") as fp:
                                fp.write(content_bytes)
                        except IOError as e:
                            print("ERROR CREATE ATTACHMENT FILE %s" % e)
                return id
        else:
            return await super().create(payload)

    @hybridmethod
    async def create_bulk(self, payload, session=None):
        async with env.apps.db.get_transaction():
            storage_id = await self._get_default_storage_id()
            for attachment in payload:
                if payload and storage_id and attachment.content:
                    content_bytes = base64.b64decode(attachment.content)
                    # в базу контент не сохраняем
                    attachment.content = None
                    attachment.storage_id = storage_id
                    filestore_path = env.settings.attachments.filestore_path
                    attachment.storage_file_url = f"{filestore_path}\\{attachment.res_model}\\{attachment.res_id}\\{attachment.name}"

                    # TODO: передеалать на pattern strategy self.storage_id.create_file
                    if storage_id.type == "file":
                        if not os.path.exists(attachment.storage_file_url):
                            try:
                                os.makedirs(
                                    os.path.dirname(
                                        attachment.storage_file_url
                                    ),
                                    exist_ok=True,
                                )
                                with open(
                                    attachment.storage_file_url, "wb"
                                ) as fp:
                                    fp.write(content_bytes)
                            except IOError as e:
                                print("ERROR CREATE ATTACHMENT FILE %s" % e)
            return await super().create_bulk(payload)
