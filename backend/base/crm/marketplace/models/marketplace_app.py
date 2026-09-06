# Copyright 2025 FARA CRM
# Marketplace module - приложение (модуль) в каталоге

from typing import TYPE_CHECKING

from backend.base.system.core.enviroment import env
from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Decimal,
    Integer,
    Selection,
    Text,
)
from backend.base.crm.security.polymorphic_parent import (
    PolymorphicParentMixin,
)
from backend.base.crm.users.audit_mixin import AuditMixin

if TYPE_CHECKING:
    from backend.base.crm.attachments.models.attachments import Attachment

CATEGORIES = [
    ("crm", "CRM"),
    ("communication", "Общение"),
    ("telephony", "Телефония"),
    ("integration", "Интеграции"),
    ("reports", "Отчёты"),
    ("other", "Прочее"),
]

# Файлы приложения — обычные вложения записи (res_model/res_id): картинки —
# скриншоты (первая — обложка), zip — архив модуля. Отдельного поля под архив
# нет: скачивается последний загруженный zip.
ARCHIVE_MIMETYPES = ["application/zip", "application/x-zip-compressed"]
IMAGE_MIMETYPE_PATTERN = "image/%"

# Поля вложения, нужные для отдачи содержимого (как в роутере вложений).
ATTACHMENT_CONTENT_FIELDS = [
    "id",
    "name",
    "mimetype",
    "storage_file_url",
    "storage_file_id",
    "storage_id",
    "content",
]


class MarketplaceApplication(AuditMixin, PolymorphicParentMixin):
    """
    Приложение в каталоге маркетплейса.

    Поставщик = create_user_id (кто создал запись): правила доступа дают ему
    править свои записи, остальным — читать опубликованные.
    """

    __table__ = "marketplace_app"

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=128, required=True, description="Название")
    summary: str | None = Char(
        max_length=255, description="Краткое описание (в карточке)"
    )
    description: str | None = Text(description="Описание")
    category: str = Selection(options=CATEGORIES, default="other")
    version: str = Char(max_length=32, default="1.0.0")
    price: float = Decimal(
        16, 2, default=0, description="Цена, ₽ (0 — бесплатно)"
    )
    published: bool = Boolean(
        default=False, description="Опубликовано в каталоге"
    )
    downloads: int = Integer(default=0, description="Скачиваний")

    @staticmethod
    def _archive_required() -> FaraException:
        return FaraException(
            {
                "content": "MARKETPLACE_ARCHIVE_REQUIRED",
                "detail": "Загрузите zip-архив модуля перед публикацией",
                "status_code": 400,
            }
        )

    @hybridmethod
    async def create(self, payload, session=None, depends_jobs=None):
        # У новой записи файлов ещё нет — публиковать нечего.
        if payload.published:
            raise self._archive_required()
        return await super().create(payload, session, depends_jobs)

    async def update(
        self, payload, fields=None, session=None, depends_jobs=None
    ):
        # Публиковать можно только с загруженным архивом модуля.
        if payload.published and not await self.get_archive():
            raise self._archive_required()
        return await super().update(payload, fields, session, depends_jobs)

    async def get_archive(self) -> "Attachment | None":
        """Последний загруженный zip приложения."""
        rows = await env.models.attachment.search(
            fields=ATTACHMENT_CONTENT_FIELDS,
            filter=[
                ("res_model", "=", self.__table__),
                ("res_id", "=", self.id),
                ("mimetype", "in", ARCHIVE_MIMETYPES),
            ],
            sort="id",
            order="desc",
            limit=1,
        )
        return rows[0] if rows else None

    @classmethod
    async def get_screenshots(cls, app_ids: list[int]) -> list["Attachment"]:
        """Картинки-вложения приложений, старые первыми (первая — обложка)."""
        if not app_ids:
            return []
        return await env.models.attachment.search(
            fields=["id", "name", "res_id", "checksum"],
            filter=[
                ("res_model", "=", cls.__table__),
                ("res_id", "in", app_ids),
                ("mimetype", "like", IMAGE_MIMETYPE_PATTERN),
            ],
            sort="id",
            order="asc",
            limit=1000,
        )
