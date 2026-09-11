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
from backend.base.crm.attachments_git.strategies.strategy import (
    fetch_archive,
    list_modules,
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
# нет: скачивается последний загруженный zip. Архив из репозитория — такое же
# вложение, только в хранилище типа git (модуль attachments_git).
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


def _category_for(code: str, info: dict) -> str:
    """Категория каталога по коду модуля и категории из его info."""
    text = f"{code} {info.get('category', '')}".lower()
    if "phone" in text or "telephony" in text:
        return "telephony"
    if "chat" in text:
        return "communication"
    if "report" in text:
        return "reports"
    if "lead" in text or "sales" in text or "partner" in text:
        return "crm"
    return "other"


class MarketplaceApplication(AuditMixin, PolymorphicParentMixin):
    """
    Приложение в каталоге маркетплейса.

    Поставщик = create_user_id (кто создал запись): правила доступа дают ему
    править свои записи, остальным — читать опубликованные.
    """

    __table__ = "marketplace_app"

    id: int = Integer(primary_key=True)
    code: str | None = Char(
        max_length=64, index=True, description="Код модуля (имя папки)"
    )
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
    # Ставит только system_admin (или суперпользователь) — тот, кто проверял.
    verified: bool = Boolean(
        default=False,
        role_create="system_admin",
        role_update="system_admin",
        description="Проверено администрацией",
    )

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
        return await env.models.attachment.search_one(
            fields=ATTACHMENT_CONTENT_FIELDS,
            filter=[
                ("res_model", "=", self.__table__),
                ("res_id", "=", self.id),
                ("mimetype", "in", ARCHIVE_MIMETYPES),
            ],
            sort="id",
            order="desc",
        )

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

    @classmethod
    async def sync_from_git(cls) -> int:
        """
        Импорт модулей из git-хранилища: по записи на каждый модуль
        репозитория (папка с app.py и словарём info; сервисы —
        инфраструктура, пропускаются) + архив-вложение «:код» на ветке
        хранилища. Известные коды не трогаются — повторный запуск добавляет
        только новые модули. Записи не публикуются: админ смотрит и
        публикует сам.
        """
        storage = await env.models.attachment_storage.search_one(
            fields=["id", "git_repo_url", "git_ref", "git_token"],
            filter=[("type", "=", "git")],
            sort="id",
            order="asc",
        )
        if not storage:
            raise FaraException(
                {
                    "content": "MARKETPLACE_GIT_STORAGE_MISSING",
                    "detail": "Нет хранилища вложений типа GitHub",
                    "status_code": 400,
                }
            )
        ref = storage.git_ref or "HEAD"
        archive = await fetch_archive(storage, ref)
        if archive is None:
            raise FaraException(
                {
                    "content": "MARKETPLACE_GIT_UNAVAILABLE",
                    "detail": (
                        "GitHub не отдал архив репозитория: проверьте "
                        "адрес, ветку и токен хранилища"
                    ),
                    "status_code": 502,
                }
            )
        existing = {
            row.code
            for row in await cls.search(fields=["id", "code"], limit=1000)
        }

        created = 0
        for code, info in list_modules(archive).items():
            if info.get("service") or code in existing:
                continue
            app_id = await cls.create(
                payload=cls(
                    code=code,
                    name=info.get("name", code),
                    summary=info.get("summary"),
                    category=_category_for(code, info),
                    version=str(info.get("version", "1.0.0")),
                    price=0,
                    verified=True,
                )
            )
            await env.models.attachment.create(
                payload=env.models.attachment(
                    name=f"{code}.zip",
                    mimetype="application/zip",
                    res_model=cls.__table__,
                    res_id=app_id,
                    storage_id=storage.id,
                    storage_file_id=f":{code}",
                    storage_file_url=f"{storage.git_repo_url}/tree/{ref}",
                    show_preview=False,
                )
            )
            created += 1
        return created
