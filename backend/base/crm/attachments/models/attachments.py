# Copyright 2025 FARA CRM
# Attachments module - Attachment model with Strategy pattern

import base64
import logging
from typing import Self, TYPE_CHECKING

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
from .attachments_storage import AttachmentStorage

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

    storage_file_id: str | None = Char(
        string="Storage file ID",
        help="File ID in cloud storage (Google Drive ID, etc.)",
    )

    storage_parent_id: str | None = Char(
        string="Storage parent ID",
        help="Parent folder ID in cloud storage",
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

    @classmethod
    async def _get_or_create_default_storage(cls) -> AttachmentStorage:
        """
        Получить активное хранилище или создать FileStore по умолчанию.

        Returns:
            Хранилище для использования
        """
        return await AttachmentStorage.get_or_create_default()

    # ========================================================================
    # CRUD методы с использованием стратегий
    # ========================================================================

    async def read_content(self) -> bytes | None:
        """
        Прочитать содержимое файла через стратегию хранения.

        Returns:
            Содержимое файла в байтах или None если файл не найден
        """
        # Если контент уже загружен - возвращаем его
        # if self.content:
        #     return self.content

        # Если нет хранилища - файл не сохранен
        if not self.storage_id:
            logger.warning(f"Attachment {self.id} has no storage configured")
            return None

        try:
            strategy = self._get_strategy()
            self.content = await strategy.read_file(self.storage_id, self)
            return self.content
        except Exception as e:
            logger.error(f"Failed to read attachment {self.id}: {e}")
            return None

    @hybridmethod
    async def create(self, payload: Self) -> int:
        """
        Создать вложение с сохранением файла через стратегию.

        Если payload содержит content (base64), файл сохраняется
        в активное хранилище через соответствующую стратегию.

        Args:
            payload: Данные для создания вложения

        Returns:
            ID созданного вложения
        """
        # Если есть контент - сохраняем через стратегию
        if payload and payload.content:
            storage = await self._get_or_create_default_storage()

            # Проверяем что стратегия зарегистрирована
            if not has_strategy(storage.type):
                logger.warning(
                    f"Strategy '{storage.type}' not found, "
                    f"falling back to basic create"
                )
                return await super().create(payload)

            async with env.apps.db.get_transaction():
                # Декодируем контент из base64
                try:
                    content_bytes = base64.b64decode(payload.content)
                except Exception as e:
                    logger.error(f"Failed to decode content: {e}")
                    raise ValueError("Invalid base64 content") from e

                # Устанавливаем хранилище
                payload.storage_id = storage
                # Устанавливаем размер если не задан
                if not payload.size:
                    payload.size = len(content_bytes)

                # Получаем стратегию и создаем файл
                strategy = get_strategy(storage.type)
                result = await strategy.create_file(
                    storage=storage,
                    attachment=payload,
                    content=content_bytes,
                    filename=payload.name or "unnamed",
                    mimetype=payload.mimetype,
                )

                # Обновляем payload данными от стратегии
                payload.storage_file_url = result.get("storage_file_url")
                payload.storage_file_id = result.get("storage_file_id")
                payload.storage_parent_id = result.get("storage_parent_id")
                payload.storage_parent_name = result.get("storage_parent_name")

                # Очищаем контент перед сохранением в БД
                # payload.content = None

                logger.info(
                    f"Creating attachment '{payload.name}' "
                    f"in storage '{storage.name}' ({storage.type})"
                )

                return await super().create(payload)

        # Без контента - просто создаем запись
        return await super().create(payload)

    async def update(
        self, payload: Self | None = None, fields: list | None = None
    ) -> None:
        """
        Обновить вложение с возможным обновлением файла через стратегию.

        Args:
            payload: Новые данные
            fields: Список полей для обновления
        """

        if not fields:
            fields = []

        # Если обновляется контент - используем стратегию
        if payload and payload.content and self.storage_id:
            async with env.apps.db.get_transaction():
                try:
                    content_bytes = base64.b64decode(payload.content)
                except Exception as e:
                    logger.error(f"Failed to decode content: {e}")
                    raise ValueError("Invalid base64 content") from e

                # Очищаем контент перед сохранением в БД
                # payload.content = None

                # Обновляем размер
                if not payload.size:
                    payload.size = len(content_bytes)

                # Обновляем файл через стратегию
                strategy = get_strategy(self.storage_id.type)
                result = await strategy.update_file(
                    storage=self.storage_id,
                    attachment=self,
                    content=content_bytes,
                    filename=(
                        payload.name if payload.name != self.name else None
                    ),
                    mimetype=payload.mimetype,
                )

                # Обновляем данные из результата
                if result.get("storage_file_url"):
                    payload.storage_file_url = result["storage_file_url"]

                await super().update(payload)
        else:
            await super().update(payload, fields)

    @hybridmethod
    async def create_bulk(
        self, payloads: list[Self], session=None
    ) -> list[int]:
        """
        Массовое создание вложений с сохранением файлов через стратегию.

        Args:
            payloads: Список данных для создания
            session: Сессия БД (опционально)

        Returns:
            Список ID созданных вложений
        """

        async with env.apps.db.get_transaction():
            storage = await self._get_or_create_default_storage()

            # Если стратегия не найдена - базовое создание
            if not has_strategy(storage.type):
                return await super().create_bulk(payloads)

            strategy = get_strategy(storage.type)

            # Обрабатываем каждое вложение
            for attachment in payloads:
                if attachment.content:
                    try:
                        content_bytes = base64.b64decode(attachment.content)
                    except Exception as e:
                        logger.error(
                            f"Failed to decode content for "
                            f"'{attachment.name}': {e}"
                        )
                        continue

                    # Устанавливаем хранилище и размер
                    attachment.storage_id = storage
                    if not attachment.size:
                        attachment.size = len(content_bytes)

                    # Создаем файл через стратегию
                    result = await strategy.create_file(
                        storage=storage,
                        attachment=attachment,
                        content=content_bytes,
                        filename=attachment.name or "unnamed",
                        mimetype=attachment.mimetype,
                    )

                    # Обновляем данными от стратегии
                    attachment.storage_file_url = result.get(
                        "storage_file_url"
                    )
                    attachment.storage_file_id = result.get("storage_file_id")
                    attachment.storage_parent_id = result.get(
                        "storage_parent_id"
                    )
                    attachment.storage_parent_name = result.get(
                        "storage_parent_name"
                    )

                    # Очищаем контент
                    # attachment.content = None

            return await super().create_bulk(payloads)

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
                    f"Failed to delete file for attachment {self.id}: {e}"
                )
                # Продолжаем удаление записи даже если файл не удален

        # Удаляем запись из БД
        return await super().delete()
