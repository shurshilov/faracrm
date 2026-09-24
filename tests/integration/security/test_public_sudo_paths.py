"""
Пути, где ручка или каскад читают и пишут под sudo после своей проверки.

- установка модуля из интерфейса (админ) и каталог маркетплейса без входа:
  опубликованное видно, неопубликованное — 404;
- отдача файла брендинга без входа: вложение и файл читаются под sudo;
- каскадное удаление детей записи под sudo: после удаления родителя
  вложение-сирота правилами уже не видно, но каскад его удаляет.

Run: pytest tests/integration/security/test_public_sudo_paths.py -v -m integration
"""

from contextlib import contextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.integration

from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.crm.attachments.models.attachments_storage import (
    AttachmentStorage,
)
from backend.base.crm.company.models.company import Company
from backend.base.crm.marketplace.models.marketplace_app import (
    MarketplaceApplication,
)
from backend.base.crm.partners.models.partners import Partner
from backend.base.crm.security.models.sessions import SystemSession
from backend.base.crm.users.models.users import SYSTEM_USER_ID, User
from backend.base.system.dotorm.dotorm.access import (
    get_access_session,
    set_access_session,
)
from tests.integration.security.test_field_access import _role_id, as_user


@contextmanager
def as_system():
    """HTTP-запрос через ASGI оставляет в контексте теста свою сессию —
    для подготовки данных после запроса ставим системную явно."""
    previous = get_access_session()
    set_access_session(SystemSession(user_id=SYSTEM_USER_ID))
    try:
        yield
    finally:
        set_access_session(previous)


@pytest_asyncio.fixture
async def alice(user_factory):
    """Обычный сотрудник (роль base_user)."""
    return await user_factory(
        name="Alice",
        login="alice",
        role_ids={"selected": [await _role_id("base_user")]},
    )


async def _market_app(name: str, published: bool) -> int:
    """Приложение каталога; публикация требует zip-архив во вложениях."""
    app_id = await MarketplaceApplication.create(
        MarketplaceApplication(name=name, code=name.lower())
    )
    await Attachment.create(
        Attachment(
            name=f"{name}.zip",
            mimetype="application/zip",
            res_model=MarketplaceApplication.__table__,
            res_id=app_id,
        )
    )
    if published:
        record = await MarketplaceApplication.get(app_id)
        await record.update(MarketplaceApplication(published=True))
    return app_id


class TestMarketplacePublic:
    async def test_install_from_ui_then_catalog_without_login(
        self, authenticated_client, app
    ):
        client, user_id, _ = authenticated_client
        # Ставить модули может суперпользователь.
        await (await User.get(user_id)).update(User(is_admin=True))

        response = await client.post("/apps/marketplace/install")
        assert response.status_code == 200
        assert "marketplace" in response.json()["installed"]

        with as_system():
            published = await _market_app("Published", published=True)
            hidden = await _market_app("Hidden", published=False)

        anon = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )
        async with anon:
            listing = await anon.get("/marketplace/apps")
            assert listing.status_code == 200
            names = [row["name"] for row in listing.json()["data"]]
            assert "Published" in names
            assert "Hidden" not in names

            card = await anon.get(f"/marketplace/apps/{published}")
            assert card.status_code == 200
            card = await anon.get(f"/marketplace/apps/{hidden}")
            assert card.status_code == 404


class TestBrandingPublic:
    async def test_logo_served_without_login(self, client, tmp_path):
        data = b"\x89PNG not really a picture"
        logo = tmp_path / "logo.png"
        logo.write_bytes(data)

        storage_id = await AttachmentStorage.create(
            AttachmentStorage(name="fs", type="file", active=True)
        )
        attachment_id = await Attachment.create(
            Attachment(
                name="logo.png",
                mimetype="image/png",
                storage_id=storage_id,
                storage_file_url=str(logo),
            )
        )
        await Company.create(
            Company(name="Branded", sequence=0, logo_id=attachment_id)
        )

        response = await client.get("/public/branding/logo_id")
        assert response.status_code == 200
        assert response.content == data
        assert response.headers["content-type"].startswith("image/png")


class TestCascadeUnderSudo:
    async def test_parent_delete_removes_orphaned_attachment(self, alice):
        """Правило «вложение видно, если виден родитель» после удаления
        родителя прячет сироту от сотрудника — каскад удаляет её под sudo."""
        async with as_user(alice):
            partner_id = await Partner.create(Partner(name="With file"))
            attachment_id = await Attachment.create(
                Attachment(
                    name="doc.pdf",
                    mimetype="application/pdf",
                    res_model=Partner.__table__,
                    res_id=partner_id,
                )
            )
            await (await Partner.get(partner_id)).delete()

        assert (
            await Attachment.search_one(
                fields=["id"], filter=[("id", "=", attachment_id)]
            )
            is None
        )
