"""
Доступ к данным в отчётах report_docx (интеграция, БД).

Что проверяем:
- контекст записи (ReportTemplate.record_context) не содержит приватных
  полей и полей с ролевым доступом (role_*) — ни у записи, ни у связей;
- контекст собирается под сессией пользователя: модель без ACL для его роли
  — отказ, а не документ;
- рендер под пользователем печатает закрытые теги пустыми;
- вложенные связи в search (батч-загрузка, тот же путь, что record_context
  и функции данных) не поднимают role_read-поля связанной модели — ни по
  явному списку fields_nested, ни по дефолту «все поля связи».

Run: pytest tests/integration/report_docx -v -m integration
"""

import io

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

docx = pytest.importorskip("docx")
pytest.importorskip("docxtpl")

from backend.base.system.dotorm.dotorm.access import AccessDenied  # noqa: E402
from backend.base.crm.attachments.models.attachments import (
    Attachment,
)  # noqa: E402
from backend.base.crm.attachments.models.attachments_storage import (  # noqa: E402
    AttachmentStorage,
)
from backend.base.crm.chat.models.chat_connector import (
    ChatConnector,
)  # noqa: E402
from backend.base.crm.report_docx.models.report_template import (  # noqa: E402
    ReportTemplate,
)
from backend.base.crm.report_docx.utils.engine import (
    DocxReportEngine,
)  # noqa: E402
from backend.base.crm.security.models.acls import AccessList  # noqa: E402
from backend.base.crm.users.models.users import User  # noqa: E402
from tests.integration.security.test_field_access import (  # noqa: E402
    _role_id,
    as_user,
)

PRIVATE_USER_FIELDS = {"password_hash", "password_salt"}
ROLE_CONNECTOR_FIELDS = {
    "webhook_url",
    "webhook_hash",
    "access_token",
    "refresh_token",
}


def _docx(*paragraphs: str) -> bytes:
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _text(docx_bytes: bytes) -> list[str]:
    return [p.text for p in docx.Document(io.BytesIO(docx_bytes)).paragraphs]


@pytest_asyncio.fixture
async def alice(user_factory):
    """Обычный сотрудник (роль base_user)."""
    return await user_factory(
        name="Alice",
        login="alice_report",
        role_ids={"selected": [await _role_id("base_user")]},
    )


# ---------------------------------------------------------------------------
# Контекст записи
# ---------------------------------------------------------------------------


def test_context_fields_skip_private_and_role_fields():
    names, nested = ReportTemplate._context_fields(User)
    assert {"name", "login"} <= set(names)
    assert not PRIVATE_USER_FIELDS & set(names)
    # role_create/role_update тоже считаются ролевыми — поле вне контекста
    assert "is_admin" not in names
    for sub in nested.values():
        assert not PRIVATE_USER_FIELDS & set(sub["fields"])

    names, nested = ReportTemplate._context_fields(ChatConnector)
    assert "name" in names
    assert not ROLE_CONNECTOR_FIELDS & set(names)
    for sub in nested.values():
        assert not ROLE_CONNECTOR_FIELDS & set(sub["fields"])


async def test_record_context_under_user_has_no_secrets(alice):
    async with as_user(alice):
        context = await ReportTemplate.record_context(User, alice.id)

    assert context["name"] == "Alice"
    assert not PRIVATE_USER_FIELDS & set(context)
    # ролевое поле в запрос не попало — в контексте пусто
    assert context.get("is_admin") is None

    rendered = DocxReportEngine.render(
        _docx("{{ name }}|{{ password_hash }}|{{ is_admin }}"), context
    )
    assert _text(rendered)[0] == "Alice||"


async def test_record_context_respects_model_acl(alice):
    """Модель без ACL для роли (access_list у base_user) — отказ."""
    async with as_user(alice):
        with pytest.raises(AccessDenied):
            await ReportTemplate.record_context(AccessList, 1)


# ---------------------------------------------------------------------------
# Вложенные связи: role_read связанной модели
# ---------------------------------------------------------------------------


async def test_nested_relation_hides_role_fields_for_user(alice):
    secret = {"client_secret": "s3cr3t"}
    # Хранилище с секретом создаёт система, вложение — сам пользователь;
    # public — иначе правило строк (видишь родителя — видишь вложение)
    # спрятало бы сиротское вложение и от него самого
    storage_id = await AttachmentStorage.create(
        AttachmentStorage(
            name="Google", type="google", google_json_credentials=secret
        )
    )
    async with as_user(alice):
        attachment_id = await Attachment.create(
            Attachment(
                name="a.txt",
                mimetype="text/plain",
                size=1,
                public=True,
                storage_id=storage_id,
            )
        )

        # прямой поиск связанной модели: поле вырезано
        storages = await AttachmentStorage.search(
            filter=[("id", "=", storage_id)],
            fields=["id", "name", "google_json_credentials"],
        )
        assert storages[0].name == "Google"
        assert storages[0].google_json_credentials is None

        # через связь с явным списком вложенных полей — тоже
        rows = await Attachment.search(
            filter=[("id", "=", attachment_id)],
            fields=["id", "storage_id"],
            fields_nested={
                "storage_id": {
                    "fields": ["id", "name", "google_json_credentials"]
                }
            },
        )
        assert rows[0].storage_id.name == "Google"
        assert rows[0].storage_id.google_json_credentials is None

        # и по дефолту «все поля связи» (без fields_nested)
        rows = await Attachment.search(
            filter=[("id", "=", attachment_id)], fields=["id", "storage_id"]
        )
        assert rows[0].storage_id.google_json_credentials is None

    # системная сессия читает секрет — это не потеря данных, а доступ
    rows = await Attachment.search(
        filter=[("id", "=", attachment_id)],
        fields=["id", "storage_id"],
        fields_nested={
            "storage_id": {"fields": ["id", "google_json_credentials"]}
        },
    )
    assert rows[0].storage_id.google_json_credentials == secret
