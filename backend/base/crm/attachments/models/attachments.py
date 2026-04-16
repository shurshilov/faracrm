# Copyright 2025 FARA CRM
# Attachments module - Attachment model with Strategy pattern
# OPTIMIZED: priority-based routing, folder cache in separate table

import asyncio
import contextlib
import hashlib
import logging
from typing import Self, TYPE_CHECKING

from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Binary,
    Char,
    Field,
    Integer,
    Boolean,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.attachments.strategies import get_strategy, has_strategy
from .attachments_storage import AttachmentStorage
from .attachments_route import AttachmentRoute

if TYPE_CHECKING:
    from backend.base.crm.attachments.strategies.strategy import (
        StorageStrategyBase,
    )

logger = logging.getLogger(__name__)


class Attachment(DotModel):
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

    def json_list(self):
        """Добавляет checksum в LIST сериализацию для cache busting."""
        result = super().json_list()
        checksum = getattr(self, "checksum", None)
        if checksum and not isinstance(checksum, Field):
            result["checksum"] = checksum
        else:
            result["checksum"] = None
        return result

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

    storage_file_id: str | None = Char(
        string="Storage file ID",
        help="File ID in cloud storage (Google Drive ID, etc.)",
    )

    storage_parent_id: str = Char(
        string="Storage parent ID",
        help="Parent folder ID in cloud storage",
        required=False,
    )

    storage_parent_name: str | None = Char(
        string="Storage parent Name",
        help="Parent folder name for display",
    )

    storage_file_url: str | None = Char(
        string="Storage file URL",
        help="URL or path to the file. Used for preview and edit.",
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

    # Виртуальное поле для содержимого (не сохраняется в БД)
    content: bytes | None = Binary(
        string="Binary content",
        store=False,
        help="Computed field, not stored in DB. Used for upload/download.",
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
                records = await model_class.search(
                    filter=[("id", "=", res_id)], limit=1
                )
                if records:
                    return records[0]
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
    async def create(self, payload: Self, session=None) -> int:
        # Нет контента или это Binary-sentinel — обычный INSERT без FS
        if (
            not payload
            or not payload.content
            or isinstance(payload.content, Binary)
        ):
            return await super().create(payload, session)

        async with env.apps.db.get_transaction():
            if not payload.size:
                payload.size = len(payload.content)
            payload.checksum = hashlib.sha1(payload.content).hexdigest()

            # TODO: убрать когда при инициализации будем заполнять None
            if isinstance(payload.res_model, Field):
                payload.res_model = None
            if isinstance(payload.res_id, Field):
                payload.res_id = None

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
                return await super().create(payload, session)

            payload.storage_id = storage
            if route:
                payload.route_id = route

            if storage.type != "file":
                payload.show_preview = False

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

            logger.info(
                "Creating attachment '%s' in storage '%s'",
                payload.name,
                storage.name,
            )

            return await super().create(payload, session)

    async def update(
        self,
        payload: Self,
        fields: list | None = None,
        session=None,
    ) -> None:
        if (
            not payload.content
            or isinstance(payload.content, Binary)
            or isinstance(self.storage_id, int)
        ):
            await super().update(payload, fields, session)
            return

        async with env.apps.db.get_transaction():
            # payload.content здесь гарантированно bytes (None и Binary отсечены выше)
            if not payload.size:
                payload.size = len(payload.content)
            payload.checksum = hashlib.sha1(payload.content).hexdigest()

            strategy = get_strategy(self.storage_id.type)
            result = await strategy.update_file(
                storage=self.storage_id,
                attachment=self,
                content=payload.content,
                filename=(payload.name if payload.name != self.name else None),
                mimetype=payload.mimetype,
            )

            if result.get("storage_file_url"):
                payload.storage_file_url = result["storage_file_url"]

            await super().update(payload, fields, session)

    @hybridmethod
    async def create_bulk(self, payloads: list[Self], session=None):
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
        # contextlib.nullcontext позволяет унифицировать ветку "своя
        # транзакция" и "используем переданную" без if/else и дублирования.
        tx = (
            env.apps.db.get_transaction()
            if session is None
            else contextlib.nullcontext(session)
        )

        async with tx as active_session:
            writable = await self._prepare_attachments(payloads)
            if writable:
                # return_exceptions=False: первая же ошибка записи валит
                # всю транзакцию. Файлы уже успешно записанных задач
                # остаются orphan'ами на диске — это отдельная тема
                # cleanup'а, не решаем здесь.
                await asyncio.gather(
                    *(
                        self._write_file(p, cb, st, pid)
                        for p, cb, st, pid in writable
                    )
                )

            return await super().create_bulk(payloads, active_session)

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
            payload.storage_parent_id = parent_id
            payload.storage_parent_name = parent_name
            if route:
                payload.route_id = route
            if storage.type != "file":
                payload.show_preview = False

            writable.append((payload, payload.content, storage, parent_id))

        return writable

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
        if result.get("storage_parent_id"):
            payload.storage_parent_id = result["storage_parent_id"]
        if result.get("storage_parent_name"):
            payload.storage_parent_name = result["storage_parent_name"]

    async def delete(self) -> bool:
        """
        Удалить вложение и файл из хранилища.

        Returns:
            True если успешно удалено
        """
        # Файл удаляется ДО записи в БД. Если не удалось — продолжаем
        # удаление из БД (orphan-файл лучше, чем orphan-запись).
        if self.storage_id and (self.storage_file_url or self.storage_file_id):
            await self._safe_delete_file()

        return await super().delete()

    @hybridmethod
    async def delete_bulk(self, ids: list[int], session=None):
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

        # Подгружаем записи, чтобы знать storage_id и пути к файлам.
        # В search() _check_access фильтрует недоступные — но delete_bulk
        # у super() делает свою проверку прав по ids, так что тут достаточно
        # просто загрузки.
        cls = self.__class__
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

        return await super().delete_bulk(ids, session)

    async def _safe_delete_file(self) -> None:
        """Удалить файл в storage, логируя ошибки вместо их проброса."""
        try:
            strategy = get_strategy(self.storage_id.type)
            await strategy.delete_file(self.storage_id, self)
        except Exception as e:
            logger.error(
                "Failed to delete file for attachment %s: %s", self.id, e
            )
