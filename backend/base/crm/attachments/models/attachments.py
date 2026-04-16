# Copyright 2025 FARA CRM
# Attachments module - Attachment model with Strategy pattern
# OPTIMIZED: priority-based routing, folder cache in separate table

import asyncio
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
    async def create_bulk(
        self, payloads: list[Self], session=None
    ) -> list[int]:
        """
        Массовое создание вложений с сохранением файлов через стратегию.
        Args:
            payloads: Список данных для создания
            session: Сессия БД (опционально). Если None — create_bulk откроет
                     свою транзакцию.

        Returns:
            Список ID созданных вложений (в порядке payloads)
        """
        # Если session передана — используем её (работаем в транзакции
        # вызывающего кода). Иначе — открываем свою для атомарности.
        if session is not None:
            return await self._create_bulk_in_session(payloads, session)

        async with env.apps.db.get_transaction() as own_session:
            return await self._create_bulk_in_session(payloads, own_session)

    @hybridmethod
    async def _create_bulk_in_session(
        self, payloads: list[Self], session
    ) -> list[int]:
        """
        Внутренняя реализация create_bulk с явной сессией.
        Разделено, чтобы не плодить ветвление внутри основного метода.
        """
        folder_cache: dict = {}

        prepared: list[tuple[Self, bytes, object, object]] = []
        # tuple = (payload, content_bytes, storage, parent_folder_id)

        for attachment in payloads:
            # Нет контента (None или Binary-sentinel) — пропускаем FS-часть,
            # payload всё равно пойдёт в bulk INSERT, но без storage_file_url.
            if not attachment.content or isinstance(
                attachment.content, Binary
            ):
                prepared.append((attachment, None, None, None))
                continue

            # content здесь гарантированно bytes — после Pydantic Base64Bytes
            # и отсева None/Binary выше.
            if not attachment.size:
                attachment.size = len(attachment.content)
            attachment.checksum = hashlib.sha1(attachment.content).hexdigest()

            route, storage, parent_folder_id, parent_folder_name = (
                await self._resolve_route_and_folder(
                    res_model=attachment.res_model,
                    res_id=attachment.res_id,
                    folder_cache=folder_cache,
                )
            )
            if not storage:
                storage = await AttachmentStorage.get_or_create_default()
            if not has_strategy(storage.type):
                # Нет стратегии — пропускаем FS-часть, payload пойдёт в
                # INSERT без storage_file_url (как fallback в старой
                # версии кода).
                prepared.append((attachment, None, None, None))
                continue

            attachment.storage_id = storage
            if route:
                attachment.route_id = route
            if storage.type != "file":
                attachment.show_preview = False
            # Заранее запоминаем storage_parent_* из resolve, FS-этап
            # может их не вернуть.
            attachment.storage_parent_id = parent_folder_id
            attachment.storage_parent_name = parent_folder_name

            prepared.append(
                (attachment, attachment.content, storage, parent_folder_id)
            )

        async def _write_one(
            payload: Self,
            content_bytes: bytes,
            storage,
            parent_folder_id,
        ) -> None:
            strategy = get_strategy(storage.type)
            result = await strategy.create_file(
                storage=storage,
                attachment=payload,
                content=content_bytes,
                filename=payload.name or "unnamed",
                mimetype=payload.mimetype,
                parent_id=parent_folder_id,
            )
            # Заполняем поля payload результатом записи
            payload.storage_file_url = result.get("storage_file_url")
            payload.storage_file_id = result.get("storage_file_id")
            if result.get("storage_parent_id"):
                payload.storage_parent_id = result.get("storage_parent_id")
            if result.get("storage_parent_name"):
                payload.storage_parent_name = result.get("storage_parent_name")

        write_tasks = [
            _write_one(p, cb, st, pid)
            for (p, cb, st, pid) in prepared
            if cb is not None  # только те, у кого есть контент и storage
        ]
        if write_tasks:
            # return_exceptions=False: если одна запись упала — падаем
            # целиком. В транзакции это приведёт к откату, а на диске
            # останутся файлы от уже завершившихся тасков (orphan'ы —
            # это отдельная тема cleanup'а, решаем не здесь).
            await asyncio.gather(*write_tasks)

        return await super().create_bulk(payloads, session)

    async def delete(self) -> bool:
        """
        Удалить вложение и файл из хранилища.

        Returns:
            True если успешно удалено
        """

        # Удаляем файл из хранилища если есть
        if self.storage_id and (self.storage_file_url or self.storage_file_id):
            try:
                strategy = get_strategy(self.storage_id.type)
                await strategy.delete_file(self.storage_id, self)
            except Exception as e:
                logger.error(
                    "Failed to delete file for attachment %s: %s", self.id, e
                )
                # Продолжаем удаление записи даже если файл не удален

        # Удаляем запись из БД
        return await super().delete()
