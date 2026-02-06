"""
Integration tests for Attachments module.

Tests cover:
- Attachment CRUD
- Attachment storage
- Polymorphic relations (res_model / res_id)

Run: pytest tests/integration/attachments/test_attachments.py -v -m integration
"""

import pytest
from requests import session

pytestmark = pytest.mark.integration


class TestAttachmentCreate:
    """Tests for attachment creation."""

    async def test_create_attachment(self, test_env):
        from backend.base.crm.attachments.models.attachments import Attachment

        aid = await test_env.models.attachment.create(
            Attachment(
                name="test.pdf",
                mimetype="application/pdf",
                size=1024,
            ),
            session=test_env.apps.db.get_session(),
        )
        a = await Attachment.get(aid)
        assert a.name == "test.pdf"
        assert a.mimetype == "application/pdf"
        assert a.size == 1024

    async def test_create_image_attachment(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        aid = await Attachment.create(
            Attachment(
                name="photo.jpg",
                mimetype="image/jpeg",
                size=2048000,
                public=True,
            )
        )
        a = await Attachment.get(aid)
        assert a.mimetype == "image/jpeg"
        assert a.public is True

    async def test_create_attachment_with_resource(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        aid = await Attachment.create(
            Attachment(
                name="avatar.png",
                mimetype="image/png",
                res_model="users",
                res_field="image",
                res_id=1,
            )
        )
        a = await Attachment.get(aid)
        assert a.res_model == "users"
        assert a.res_field == "image"
        assert a.res_id == 1

    async def test_create_folder(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        aid = await Attachment.create(
            Attachment(
                name="Documents",
                folder=True,
            )
        )
        a = await Attachment.get(aid)
        assert a.folder is True

    async def test_create_with_storage_url(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        aid = await Attachment.create(
            Attachment(
                name="cloud_file.pdf",
                storage_file_url="https://storage.example.com/files/abc123",
                storage_file_id="abc123",
            )
        )
        a = await Attachment.get(aid)
        assert a.storage_file_url == "https://storage.example.com/files/abc123"
        assert a.storage_file_id == "abc123"


class TestAttachmentRead:
    """Tests for reading attachments."""

    async def test_search_attachments(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        for i in range(5):
            await Attachment.create(Attachment(name=f"file_{i}.txt"))
        atts = await Attachment.search(fields=["id", "name"])
        assert len(atts) == 5

    async def test_search_by_mimetype(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        await Attachment.create(
            Attachment(name="doc.pdf", mimetype="application/pdf")
        )
        await Attachment.create(
            Attachment(name="img.png", mimetype="image/png")
        )
        await Attachment.create(
            Attachment(name="doc2.pdf", mimetype="application/pdf")
        )

        pdfs = await Attachment.search(
            fields=["id", "name"],
            filter=[("mimetype", "=", "application/pdf")],
        )
        assert len(pdfs) == 2

    async def test_search_by_resource(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        await Attachment.create(
            Attachment(name="a1", res_model="users", res_id=1)
        )
        await Attachment.create(
            Attachment(name="a2", res_model="users", res_id=1)
        )
        await Attachment.create(
            Attachment(name="a3", res_model="partners", res_id=1)
        )

        user_atts = await Attachment.search(
            fields=["id", "name"],
            filter=[("res_model", "=", "users"), ("res_id", "=", 1)],
        )
        assert len(user_atts) == 2

    async def test_search_public_only(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        await Attachment.create(Attachment(name="public.pdf", public=True))
        await Attachment.create(Attachment(name="private.pdf", public=False))

        public = await Attachment.search(
            fields=["id", "name"],
            filter=[("public", "=", True)],
        )
        assert len(public) == 1
        assert public[0].name == "public.pdf"


class TestAttachmentUpdate:
    """Tests for updating attachments."""

    async def test_rename_attachment(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        aid = await Attachment.create(Attachment(name="old_name.pdf"))
        a = await Attachment.get(aid)
        await a.update(Attachment(name="new_name.pdf"))
        updated = await Attachment.get(aid)
        assert updated.name == "new_name.pdf"

    async def test_make_public(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        aid = await Attachment.create(
            Attachment(name="test.pdf", public=False)
        )
        a = await Attachment.get(aid)
        await a.update(Attachment(public=True))
        updated = await Attachment.get(aid)
        assert updated.public is True


class TestAttachmentDelete:
    """Tests for deleting attachments."""

    async def test_delete_attachment(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        aid = await Attachment.create(Attachment(name="delete_me.pdf"))
        a = await Attachment.get(aid)
        await a.delete()
        assert await Attachment.get_or_none(aid) is None

    async def test_bulk_delete(self):
        from backend.base.crm.attachments.models.attachments import Attachment

        ids = [
            await Attachment.create(Attachment(name=f"bulk_{i}.txt"))
            for i in range(5)
        ]
        await Attachment.delete_bulk(ids)
        for aid in ids:
            assert await Attachment.get_or_none(aid) is None
