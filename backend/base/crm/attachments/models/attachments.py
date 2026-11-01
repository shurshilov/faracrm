# Copyright 2025 FARA CRM
# Attachments module - Attachment model with Strategy pattern
# OPTIMIZED: priority-based routing, folder cache in separate table

import asyncio
import contextlib
import hashlib
import logging
from typing import Self, TYPE_CHECKING

from backend.base.system.dotorm.dotorm.access import Operation
from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Binary,
    Char,
    Integer,
    Boolean,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.attachments.strategies import get_strategy, has_strategy
from backend.base.crm.users.audit_mixin import AuditMixin
from .attachments_storage import AttachmentStorage
from .attachments_route import AttachmentRoute
from .attachments_upload import AttachmentUpload, ContentNotSupported

if TYPE_CHECKING:
    from backend.base.crm.attachments.strategies.strategy import (
        StorageStrategyBase,
    )

logger = logging.getLogger(__name__)

# Сигнатуры (magic bytes) файлов, которые просмотр показывает inline:
# (смещение, первые байты, семейство). Порядок важен — берётся первая
# подошедшая: HEIC и AVIF — картинки в том же контейнере ftyp, что и mp4
SIGNATURES = (
    # --- СЕМЕЙСТВО DOCS / PDF ---
    (0, b"%PDF-", "pdf"),  # application/pdf
    # --- СЕМЕЙСТВО IMAGE (БЕЗОПАСНЫЕ КАРТИНКИ) ---
    # Внимание: image/svg+xml СУДА НЕ ДОБАВЛЯЕТСЯ, так как содержит XML/JS и опасен для inline
    (0, b"\x89PNG", "image"),  # image/png
    (0, b"\xff\xd8\xff", "image"),  # image/jpeg
    (0, b"GIF8", "image"),  # image/gif
    (8, b"WEBP", "image"),  # image/webp (внутри контейнера RIFF)
    (0, b"BM", "image"),  # image/bmp
    (0, b"II*\x00", "image"),  # image/tiff (Intel byte order)
    (0, b"MM\x00*", "image"),  # image/tiff (Motorola byte order)
    (
        0,
        b"\x00\x00\x01\x00",
        "image",
    ),  # image/x-icon / image/vnd.microsoft.icon
    (8, b"heic", "image"),  # image/heic
    (8, b"heix", "image"),  # image/heic (вариация)
    (8, b"mif1", "image"),  # image/heif
    (8, b"avif", "image"),  # image/avif
    # --- СЕМЕЙСТВО MEDIA (БЕЗОПАСНЫЕ АУДИО И ВИДЕО) ---
    # Видео-контейнеры и базовые форматы
    (
        4,
        b"ftyp",
        "media",
    ),  # video/mp4, audio/mp4, video/quicktime (mov), audio/m4a, video/3gpp
    (
        0,
        b"\x1a\x45\xdf\xa3",
        "media",
    ),  # video/webm, audio/webm, video/x-matroska (mkv)
    (0, b"OggS", "media"),  # audio/ogg, video/ogg, application/ogg
    # Чистый MP3 (audio/mpeg)
    (0, b"ID3", "media"),  # MP3 с тегами ID3v2
    (0, b"\xff\xfb", "media"),  # MP3 без тегов (MPEG-1 Layer 3)
    (0, b"\xff\xf3", "media"),  # MP3 без тегов (MPEG-2 Layer 3)
    (0, b"\xff\xf2", "media"),  # MP3 без тегов (MPEG-2.5 Layer 3)
    (0, b"\xff\xfa", "media"),  # Дополнительные фреймы MP3
    (0, b"\xff\xf9", "media"),
    (0, b"\xff\xe3", "media"),
    # Чистый AAC (audio/aac)
    (0, b"\xff\xf1", "media"),  # AAC ADTS (MPEG-4, без защиты)
    (0, b"\xff\xf0", "media"),  # AAC ADTS (MPEG-4, с защитой CRC)
    (0, b"\xff\xf9", "media"),  # AAC ADTS (MPEG-2, без защиты)
    (0, b"\xff\xf8", "media"),  # AAC ADTS (MPEG-2, с защитой CRC)
    (0, b"ADIF", "media"),  # Rare AAC ADIF формат
    # Другие популярные аудиоформаты
    (0, b"fLaC", "media"),  # audio/flac
    (0, b"#!AMR", "media"),  # audio/amr
    (0, b"MThd", "media"),  # audio/midi
    # Обработка контейнеров RIFF (WAV, AVI и гибриды вроде RIFF-MP3)
    (8, b"WAVE", "media"),  # audio/wav / audio/x-wav
    (8, b"AVI ", "media"),  # video/x-msvideo (avi)
    (
        0,
        b"RIFF",
        "media",
    ),  # Запасной вариант для RIFF-MP3, старых AVI и WebP без смещения
)


def mimetype_essence(mimetype: str | None) -> str:
    """Тип без параметров и регистра: «Image/SVG+XML; charset=utf-8» браузер
    покажет как image/svg+xml — сравнивать типы можно только в таком виде."""
    return (mimetype or "").split(";", 1)[0].strip().lower()


def _inline_family(mimetype: str | None) -> str | None:
    """
    Семейство типа, который просмотр показывает inline и который можно подтвердить сигнатурой;
    None — у типа нет сигнатуры или он не inline (безопасный офис, архивы).
    "unsafe" — тип опасен для inline (HTML, SVG, XML), его нужно принудительно качать.
    """
    mimetype = mimetype or ""

    # 1. ЗАЩИТА: Явно отлавливаем опасные форматы, способные исполнять скрипты
    if mimetype in (
        "text/html",
        "image/svg+xml",
        "text/xml",
        "application/xml",
    ):
        return "unsafe"

    if mimetype == "application/pdf":
        return "pdf"

    if mimetype.startswith("image/"):  # SVG мы уже отсекли выше
        return "image"

    if mimetype.startswith(("audio/", "video/")):
        return "media"

    return None


def _signature_family(content: bytes) -> str | None:
    """Семейство по первым байтам файла; None — сигнатуры нет в таблице."""
    for offset, magic, family in SIGNATURES:
        if content.startswith(magic, offset):
            return family
    return None


def inline_mimetype(content: bytes, declared: str | None) -> str | None:
    """Тип присылает клиент или мессенджер, подделать его ничего не стоит.
    Тип, который браузер покажет inline, должен подтвердиться первыми
    байтами файла (magic bytes), иначе файл отдаётся скачиванием. Тип
    хранится без параметров: с ними точные сравнения типа не срабатывают."""
    declared = mimetype_essence(declared) or None
    family = _inline_family(declared)
    if family is None:
        return declared  # текст, офис, архивы
    if _signature_family(content) == family:
        return declared
    return "application/octet-stream"


class Attachment(AuditMixin, DotModel):
    """
    Модель вложений с поддержкой различных стратегий хранения.

    Использует паттерн Strategy для работы с различными хранилищами:
    - FileStore (локальные файлы)
    - Google Drive
    - OneDrive
    - и другие

    Стратегия выбирается автоматически на основе активного хранилища
    или хранилища, связанного с конкретным вложением.
    """

    __table__ = "attachments"

    # Составные индексы: (res_model, res_id) — для полиморфной выборки
    # всех вложений конкретной записи (основной паттерн доступа).
    __indexes__ = [("res_model", "res_id")]

    # Полиморфный ребёнок: каждая модель получает поле-связь attachment_ids
    # (файлы записи, без папок) автоматически — см.
    # ModelsCore._attach_polymorphic_fields. ChatMessage объявляет своё.
    __polymorphic_field__ = ("attachment_ids", [("folder", "=", False)])

    def json_list(self):
        """Добавляет checksum в LIST сериализацию для cache busting."""
        result = super().json_list()
        # Под non-data descriptor self.checksum возвращает либо реальное
        # значение, либо None (если не назначено). Поэтому просто truthy.
        checksum = self.checksum
        result["checksum"] = checksum if checksum else None
        return result

    def serialize_for_chat(self) -> dict:
        """Форма вложения для чата — единый вид для REST-списка (/messages) и
        WS-пуша входящего вложения (strategy.save_attachments), чтобы фронт
        рендерил их одинаково. Ожидает поля
        id/name/mimetype/size/checksum/is_voice/show_preview.
        """
        return {
            "id": self.id,
            "name": self.name,
            "mimetype": self.mimetype,
            "size": self.size,
            "checksum": self.checksum,
            "is_voice": self.is_voice or False,
            "show_preview": self.show_preview,
        }

    id: int = Integer(primary_key=True)

    name: str = Char(
        string="Filename",
        help="Name of the file",
    )

    res_model: str | None = Char(
        string="Resource Model",
        help="Model name this attachment is linked to",
    )

    res_field: str | None = Char(
        string="Resource Field",
        help="Field name this attachment is linked to",
    )

    res_id: int | None = Integer(
        string="Resource ID",
        help="Record ID this attachment is linked to",
    )

    public: bool = Boolean(
        string="Is public document",
        default=False,
    )

    folder: bool = Boolean(
        string="Is folder",
        default=False,
    )

    access_token: str | None = Char(
        string="Access Token",
        help="Token for public access",
    )

    size: int = Integer(
        string="File Size",
        help="Size in bytes",
    )

    checksum: str | None = Char(
        string="Checksum/SHA1",
        max_length=40,
    )

    mimetype: str | None = Char(
        string="Mime Type",
    )

    storage_id: AttachmentStorage | None = Many2one(
        relation_table=AttachmentStorage,
        string="Storage",
        help="Storage where file is saved",
    )

    route_id: AttachmentRoute | None = Many2one(
        relation_table=AttachmentRoute,
        string="Route",
        help="Route used to organize file in folders",
    )

    # role_create/role_update на storage_file_id/storage_parent_id/
    # storage_file_url: где лежит файл, решает только сервер — иначе клиент
    # указал бы чужой путь на диске или чужой файл в облаке и скачал его.
    storage_file_id: str | None = Char(
        string="Storage file ID",
        help="File ID in cloud storage (Google Drive ID, etc.)",
        role_create="system_admin",
        role_update="system_admin",
    )

    storage_parent_id: str = Char(
        string="Storage parent ID",
        help="Parent folder ID in cloud storage",
        required=False,
        role_create="system_admin",
        role_update="system_admin",
    )

    storage_parent_name: str | None = Char(
        string="Storage parent Name",
        help="Parent folder name for display",
    )

    storage_file_url: str | None = Char(
        string="Storage file URL",
        help="URL or path to the file. Used for preview and edit.",
        role_create="system_admin",
        role_update="system_admin",
    )

    is_voice: bool = Boolean(
        default=False,
        string="Is voice message",
        help="True if attachment is a voice recording from chat",
    )

    show_preview: bool = Boolean(
        default=True,
        string="Show preview",
        help="Show preview in kanban by default. "
        "For cloud storages (type != 'file') defaults to False.",
    )

    # Виртуальное поле для содержимого (не сохраняется в БД). В API файл
    # приходит загрузкой частями (upload_id), content — ошибка 400
    content: bytes | None = Binary(
        string="Binary content",
        store=False,
        schema_type=ContentNotSupported,
        help="Computed field, not stored in DB. Used for upload/download.",
    )

    # Вместо content — готовая загрузка частями (AttachmentUpload.fill)
    upload_id: int | None = Integer(
        string="Upload ID",
        store=False,
        help="Not stored in DB. Finished chunked upload "
        "(POST /attachments/uploads) used as file content.",
    )

    # ========================================================================
    # Методы для работы со стратегиями
    # ========================================================================

    def _get_strategy(self) -> "StorageStrategyBase":
        """
        Получить стратегию хранения для этого вложения.

        Returns:
            Экземпляр стратегии

        Raises:
            ValueError: Если хранилище не настроено или стратегия не найдена
        """

        if not self.storage_id or not self.storage_id.type:
            raise ValueError(
                f"Attachment {self.id} has no storage_id configured"
            )
        return get_strategy(self.storage_id.type)

    # ========================================================================
    # Route and folder resolution
    # ========================================================================

    async def _get_record(self, res_model: str, res_id: int):
        try:
            model_name = env.models._get_model_name_by_table(res_model)
            model_class = env.models._get_model(model_name)
            if model_class:
                return await model_class.search_one(
                    filter=[("id", "=", res_id)]
                )
        except Exception as e:
            logger.debug(
                "Could not get record %s/%s: %s", res_model, res_id, e
            )
        return None

    async def _resolve_route_and_folder(
        self,
        res_model: str | None,
        res_id: int | None,
        folder_cache: dict[tuple, dict[str, str]] | None = None,
    ):
        """
        Единая логика определения маршрута, хранилища и parent folder.

        Args:
            res_model: Модель записи
            res_id: ID записи
            folder_cache: Локальный кеш для batch операций

        Returns:
            Tuple (route, storage, parent_folder_id, parent_folder_name)
        """
        # if not res_model or not res_id:
        #     return None, None, None, None

        # 1. Находим маршрут (priority-based)
        route = await AttachmentRoute.get_route_for_attachment(
            res_model=res_model,
            res_id=res_id,
        )

        if not route:
            raise ValueError("Cant setup empty route")

        # 2. Получаем storage из route
        storage = route.storage_id
        if not storage or not storage.active:
            logger.warning("Route %s has no active storage", route.id)
            raise ValueError("Cant setup empty storage")

        # 3. Проверяем локальный кеш batch'а (только для create_bulk)
        cache_key = (res_model, res_id, route.id)
        if folder_cache is not None and cache_key in folder_cache:
            folder_id, folder_name = folder_cache[cache_key]
            return route, storage, folder_id, folder_name

        # 4. Создаём папку через API (root folders кешируются в attachments_cache)
        if res_model and res_id:
            record = await self._get_record(res_model, res_id)
            folder_id, folder_name = await route.get_or_create_record_folder(
                storage=storage,
                record=record,
                res_id=res_id,
                res_model=res_model,
            )
        else:
            folder_id, folder_name = await route.get_or_create_root_folder(
                storage, "default"
            )

        # Сохраняем в локальный кеш batch'а
        if folder_cache is not None:
            folder_cache[cache_key] = (folder_id, folder_name)

        return route, storage, folder_id, folder_name

    # ========================================================================
    # CRUD методы с использованием стратегий
    # ========================================================================

    async def read_content(self) -> bytes | None:
        """
        Прочитать содержимое файла через стратегию хранения.

        Returns:
            Содержимое файла в байтах или None если файл не найден
        """
        if not self.storage_id:
            logger.warning("Attachment %s has no storage configured", self.id)
            return None

        try:
            strategy = self._get_strategy()
            self.content = await strategy.read_file(self.storage_id, self)
            return self.content
        except Exception as e:
            logger.error("Failed to read attachment %s: %s", self.id, e)
            return None

    @hybridmethod
    async def create(
        self, payload: Self, session=None, depends_jobs=None
    ) -> int:
        uploads = await AttachmentUpload.fill([payload])
        # Нет контента или это Binary-sentinel — обычный INSERT без FS
        if (
            not payload
            or not payload.content
            or isinstance(payload.content, Binary)
        ):
            return await super().create(payload, session, depends_jobs)

        async with env.apps.db.get_transaction():
            if not payload.size:
                payload.size = len(payload.content)
            payload.checksum = hashlib.sha1(payload.content).hexdigest()
            payload.mimetype = inline_mimetype(
                payload.content, payload.mimetype
            )

            route, storage, parent_folder_id, parent_folder_name = (
                await self._resolve_route_and_folder(
                    res_model=payload.res_model,
                    res_id=payload.res_id,
                )
            )

            if not storage:
                storage = await AttachmentStorage.get_or_create_default()

            if not has_strategy(storage.type):
                logger.warning("Strategy '%s' not found", storage.type)
                return await super().create(payload, session, depends_jobs)

            payload.storage_id = storage
            if route:
                payload.route_id = route

            if storage.type != "file":
                payload.show_preview = False

            logger.info(
                "Creating attachment '%s' in storage '%s'",
                payload.name,
                storage.name,
            )

            # Сначала INSERT: id записи входит в путь файла, поэтому путь
            # уникален по построению (имя файла задаёт отправитель, и
            # «Договор.pdf» приходит постоянно). Упадёт запись файла —
            # транзакция откатит и строку.
            payload.id = await super().create(payload, session, depends_jobs)

            strategy = get_strategy(storage.type)
            result = await strategy.create_file(
                storage=storage,
                attachment=payload,
                content=payload.content,
                filename=payload.name or "unnamed",
                mimetype=payload.mimetype,
                parent_id=parent_folder_id,
            )

            payload.storage_file_url = result.get("storage_file_url")
            payload.storage_file_id = result.get("storage_file_id")
            payload.storage_parent_id = (
                result.get("storage_parent_id") or parent_folder_id
            )
            payload.storage_parent_name = (
                result.get("storage_parent_name") or parent_folder_name
            )
            await self._save_storage_fields([payload], session)
            await AttachmentUpload.release(uploads)

            return payload.id

    async def update(
        self,
        payload: Self,
        fields: list | None = None,
        session=None,
        depends_jobs=None,
    ) -> None:
        uploads = await AttachmentUpload.fill([payload])
        if (
            not payload.content
            or isinstance(payload.content, Binary)
            or isinstance(self.storage_id, int)
        ):
            await super().update(payload, fields, session, depends_jobs)
            return

        async with env.apps.db.get_transaction():
            # payload.content здесь гарантированно bytes (None и Binary отсечены выше)
            payload.size = len(payload.content)
            payload.checksum = hashlib.sha1(payload.content).hexdigest()
            # Новый файл мог прийти без типа — проверяется прежний
            payload.mimetype = inline_mimetype(
                payload.content, payload.mimetype or self.mimetype
            )
            # size, checksum и тип считает сервер, а PUT автокруда передаёт
            # только присланные поля — иначе они не запишутся
            if fields:
                fields = [*fields, "size", "checksum", "mimetype"]

            # Сначала строка: права и закрытые поля проверяет UPDATE, и до
            # диска дело доходит, только если он прошёл. Сбой записи файла
            # откатит транзакцию вместе с ним
            await super().update(payload, fields, session, depends_jobs)

            # Содержимое меняется на месте, без переименования в хранилище:
            # путь в базе остаётся верным, а имя пользователю отдаётся из
            # базы (attachment.name)
            strategy = get_strategy(self.storage_id.type)
            await strategy.update_file(
                storage=self.storage_id,
                attachment=self,
                content=payload.content,
                mimetype=payload.mimetype,
            )
            await AttachmentUpload.release(uploads)

    @hybridmethod
    async def create_bulk(
        self, payloads: list[Self], session=None, depends_jobs=None
    ):
        """
        Массовое создание вложений с сохранением файлов через стратегию.

        Этапы:
        1. Подготовка: для каждого payload резолвим folder/storage и
           считаем checksum. Последовательно, потому что folder_cache
           неэффективен при race.
        2. Запись файлов на диск — параллельно через asyncio.gather.
           Это основное I/O: 5 файлов × 10 МБ ≈ 3x быстрее на SSD.
        3. Один bulk INSERT.

        Транзакция: если session передана — используем её (работаем в
        транзакции вызывающего кода). Иначе открываем свою для атомарности
        файлов и INSERT.
        """
        uploads = await AttachmentUpload.fill(payloads)
        # contextlib.nullcontext позволяет унифицировать ветку "своя
        # транзакция" и "используем переданную" без if/else и дублирования.
        tx = (
            env.apps.db.get_transaction()
            if session is None
            else contextlib.nullcontext(session)
        )

        async with tx as active_session:
            writable = await self._prepare_attachments(payloads)

            # INSERT идёт ПЕРВЫМ: id записи входит в путь файла (см.
            # FileStoreStrategy._get_file_path), поэтому путь уникален по
            # построению. super().create_bulk проставляет id в payload'ы.
            records = await super().create_bulk(
                payloads, active_session, depends_jobs
            )

            if writable:
                # return_exceptions=False: первая же ошибка записи валит
                # всю транзакцию вместе со вставленными строками.
                await asyncio.gather(
                    *(
                        self._write_file(p, cb, st, pid)
                        for p, cb, st, pid in writable
                    )
                )
                await self._save_storage_fields(
                    [p for p, *_ in writable], active_session
                )
                await AttachmentUpload.release(uploads)

            return records

    async def _prepare_attachments(
        self, payloads: list[Self]
    ) -> list[tuple[Self, bytes, "AttachmentStorage", str | None]]:
        """
        Подготовка: checksum, resolve folder/storage.

        Возвращает список payload'ов, готовых к записи файла на диск:
        (payload, content_bytes, storage, parent_folder_id).
        Payload'ы без контента или без стратегии сюда не попадают —
        они просто идут в bulk INSERT без storage_file_url.
        """
        folder_cache: dict = {}
        writable: list = []

        for payload in payloads:
            # Нет контента — только INSERT, файл не пишем
            if not payload.content or isinstance(payload.content, Binary):
                continue

            if not payload.size:
                payload.size = len(payload.content)
            payload.checksum = hashlib.sha1(payload.content).hexdigest()
            payload.mimetype = inline_mimetype(
                payload.content, payload.mimetype
            )

            route, storage, parent_id, parent_name = (
                await self._resolve_route_and_folder(
                    res_model=payload.res_model,
                    res_id=payload.res_id,
                    folder_cache=folder_cache,
                )
            )
            if not storage:
                storage = await AttachmentStorage.get_or_create_default()
            if not has_strategy(storage.type):
                # Нет стратегии — INSERT без файла (старое fallback-поведение)
                continue

            payload.storage_id = storage
            payload.storage_parent_name = parent_name
            if route:
                payload.route_id = route
            if storage.type != "file":
                payload.show_preview = False

            writable.append((payload, payload.content, storage, parent_id))

        return writable

    @classmethod
    async def _save_storage_fields(cls, payloads: list[Self], session) -> None:
        """
        Дописать пути хранилища: они известны только после записи файла, а
        файл пишется после INSERT (путь содержит id записи).

        Одним запросом: update_bulk для этого не годится — он применяет ОДИН
        набор значений ко всем id, а путь у каждого вложения свой.
        """
        if not payloads:
            return

        # session может не прийти: create() открывает транзакцию контекстом и
        # наружу передаёт None. _get_db_session берёт явную сессию, иначе — из
        # контекста текущей транзакции (так же делают update/create_bulk).
        session = cls._get_db_session(session)

        await session.execute(
            f"""
            UPDATE {cls.__table__} AS a
               SET storage_file_url = v.url,
                   storage_file_id = v.file_id,
                   storage_parent_id = v.parent_id,
                   storage_parent_name = v.parent_name
              FROM unnest(%s::int[], %s::text[], %s::text[],
                          %s::text[], %s::text[])
                   AS v(id, url, file_id, parent_id, parent_name)
             WHERE a.id = v.id
            """,
            (
                [p.id for p in payloads],
                [p.storage_file_url for p in payloads],
                [p.storage_file_id for p in payloads],
                [p.storage_parent_id for p in payloads],
                [p.storage_parent_name for p in payloads],
            ),
            cursor="void",
        )

    async def _write_file(
        self,
        payload: Self,
        content_bytes: bytes,
        storage: "AttachmentStorage",
        parent_id: str | None,
    ) -> None:
        """Запись одного файла через стратегию + проставление путей в payload."""
        strategy = get_strategy(storage.type)
        result = await strategy.create_file(
            storage=storage,
            attachment=payload,
            content=content_bytes,
            filename=payload.name or "unnamed",
            mimetype=payload.mimetype,
            parent_id=parent_id,
        )
        payload.storage_file_url = result.get("storage_file_url")
        payload.storage_file_id = result.get("storage_file_id")
        payload.storage_parent_id = (
            result.get("storage_parent_id") or parent_id
        )
        if result.get("storage_parent_name"):
            payload.storage_parent_name = result["storage_parent_name"]

    async def delete(self, session=None, depends_jobs=None) -> bool:
        """
        Удалить вложение и файл из хранилища.

        Returns:
            True если успешно удалено
        """
        # Права — до удаления файла (super().delete проверит их уже после).
        # Файл удаляется ДО записи в БД. Если не удалось — продолжаем
        # удаление из БД (orphan-файл лучше, чем orphan-запись).
        await self._check_access(Operation.DELETE, record_ids=[self.id])
        if self.storage_id and (self.storage_file_url or self.storage_file_id):
            await self._safe_delete_file()

        return await super().delete(session, depends_jobs)

    @hybridmethod
    async def delete_bulk(
        self, ids: list[int], session=None, depends_jobs=None
    ):
        """
        Массовое удаление вложений с очисткой файлов в хранилище.

        Семантика такая же, как у одиночного delete:
        - файл удаляется до записи в БД;
        - если удаление файла упало — запись всё равно удаляется из БД
          (лучше orphan-файл, чем orphan-запись: файл подчистит background
          cleanup, а бесполезная запись в БД никому не нужна).

        Файлы удаляются параллельно через asyncio.gather — это основное I/O.
        """
        if not ids:
            return

        # Права — до удаления файлов: отказ в super().delete_bulk оставил бы
        # строки без файлов.
        cls = self.__class__
        await cls._check_access(Operation.DELETE, record_ids=ids)

        # Подгружаем записи, чтобы знать storage_id и пути к файлам.
        records = await cls.search(filter=[("id", "in", ids)])

        file_tasks = [
            r._safe_delete_file()
            for r in records
            if r.storage_id and (r.storage_file_url or r.storage_file_id)
        ]
        if file_tasks:
            # return_exceptions=True: ошибки логируются внутри
            # _safe_delete_file, а bulk DELETE в БД всё равно выполнится.
            await asyncio.gather(*file_tasks)

        return await super().delete_bulk(ids, session, depends_jobs)

    async def _safe_delete_file(self) -> None:
        """Удалить файл в storage, логируя ошибки вместо их проброса."""
        try:
            strategy = get_strategy(self.storage_id.type)
            await strategy.delete_file(self.storage_id, self)
        except Exception as e:
            logger.error(
                "Failed to delete file for attachment %s: %s", self.id, e
            )
