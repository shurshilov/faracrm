# Copyright 2025 FARA CRM
# Attachments module - FileStore (local filesystem) strategy

import re
import unicodedata

import aiofiles
import aiofiles.os
import asyncio
import os
import hashlib
import logging
from typing import TYPE_CHECKING, Any

from .strategy import StorageStrategyBase
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.attachments.models.attachments_storage import (
        AttachmentStorage,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)


# Символы, которые ВСЕГДА удаляем из имени файла:
# - \x00..\x1F и \x7F — control chars (включая NULL, \n, \t, \r),
#   ломают open(), шеллы, логи, заголовки HTTP.
# - / и \ — path separators, иначе path traversal.
# - <>:"|?* — Windows-reserved символы (для кросс-платформенности).
_FORBIDDEN_FILENAME_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*]')

# Windows-reserved базовые имена (без расширения, регистронезависимо).
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# Максимальная длина имени файла в БАЙТАХ для большинства FS
# (ext4, NTFS, APFS, XFS — все 255).
_MAX_FILENAME_BYTES = 255


def sanitize_filename(filename: str, fallback: str = "file") -> str:
    """
    Минимальная очистка имени файла под современные best practices.

    Принципы (state of the art 2024-2026; см. pathvalidate, npm
    sanitize-filename, S3/GDrive guidelines):
    - Удаляем ТОЛЬКО то, что реально опасно или невалидно для FS:
      control chars, path separators, Windows-reserved символы.
    - Сохраняем максимум исходного: кириллицу, любой Unicode,
      эмодзи, пробелы, скобки, точки внутри имени.
    - Нормализуем в NFC (каноничная форма для FS, рекомендация W3C).
      NFKD — НЕ годится: разваливает символы и в паре с
      .encode("ascii", "ignore") убивает кириллицу полностью.
    - Защита от path traversal через os.path.basename.
    - Лимит длины — в БАЙТАХ (255), а не символах: один UTF-8 символ
      может занимать до 4 байт, обрезка по символам некорректна.
    - Fallback для пустого результата, ".", "..", только-точек/пробелов.
    - Windows-reserved имена (CON, PRN, NUL, COM1..LPT9) префиксуем
      подчёркиванием, чтобы файл создавался корректно везде.

    Args:
        filename: исходное имя (может содержать что угодно от пользователя).
        fallback: что подставить, если после очистки ничего не осталось.

    Returns:
        Безопасное имя файла, валидное на ext4/NTFS/APFS.
    """
    # 1. Path traversal: оставляем только базовое имя
    filename = os.path.basename(filename or "")

    # 2. NFC: каноничная форма (НЕ NFKD — тот разваливает символы)
    filename = unicodedata.normalize("NFC", filename)

    # 3. Удаляем только реально опасные символы
    filename = _FORBIDDEN_FILENAME_CHARS.sub("", filename)

    # 4. Trailing/leading whitespace и точки на конце ломают Windows
    filename = filename.strip().rstrip(".")

    # 5. Спецслучаи "." / ".." / пусто
    if filename in ("", ".", ".."):
        return fallback

    # 6. Windows-reserved (CON, PRN, NUL, LPT1...) — префикс
    name, ext = os.path.splitext(filename)
    if name.upper() in _WINDOWS_RESERVED_NAMES:
        name = f"_{name}"
        filename = f"{name}{ext}"

    # 7. Обрезка до 255 байт с сохранением расширения и валидного UTF-8
    encoded = filename.encode("utf-8")
    if len(encoded) > _MAX_FILENAME_BYTES:
        ext_bytes = ext.encode("utf-8")
        max_name_bytes = _MAX_FILENAME_BYTES - len(ext_bytes)
        if max_name_bytes <= 0:
            # Экзотика: расширение само длиннее лимита — режем целиком
            filename = encoded[:_MAX_FILENAME_BYTES].decode(
                "utf-8", errors="ignore"
            )
        else:
            name_bytes = name.encode("utf-8")[:max_name_bytes]
            # errors="ignore" срежет хвостовой битый UTF-8
            name = name_bytes.decode("utf-8", errors="ignore")
            filename = f"{name}{ext}"

    # 8. После всех манипуляций имя могло опять стать пустым
    return filename or fallback


# Backward-compatible alias: старое имя для импортов извне модуля.
# Внутри модуля и в новом коде — звать sanitize_filename напрямую.
slugify_filename = sanitize_filename


class FileStoreStrategy(StorageStrategyBase):
    """
    Стратегия хранения файлов в локальной файловой системе.

    Файлы сохраняются в структуре:
        filestore/
        └── <parent_id>/
            └── <filename>

    Attributes:
        strategy_type: "file"
    """

    strategy_type = "file"

    # Путь по умолчанию (fallback если system_settings недоступен)
    DEFAULT_FILESTORE_PATH = os.path.join(os.getcwd(), "filestore")

    # Кеш пути — чтобы не ходить в БД на каждый файл
    _cached_path: str | None = None

    async def _get_base_path(self, storage: "AttachmentStorage") -> str:
        """Get base path for file storage from system_settings."""
        if self._cached_path is not None:
            return self._cached_path
        try:
            path = await env.models.system_settings.get_value(
                "attachments.filestore_path", self.DEFAULT_FILESTORE_PATH
            )
            self._cached_path = str(path)
            return self._cached_path
        except Exception:
            return self.DEFAULT_FILESTORE_PATH

    def _compute_checksum(self, content: bytes) -> str:
        """Compute SHA1 checksum of content."""
        return hashlib.sha1(content).hexdigest()

    async def _get_file_path(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        filename: str,
        parent_id: str,
        checksum: str | None = None,
    ) -> str:
        """
        Build file path for storage.

        Structure: filestore/<parent_id>/<filename>
        """
        base_path = await self._get_base_path(storage)
        # Безопасное имя файла (Path Traversal Protection)
        safe_name = os.path.basename(filename)

        parts = [base_path]
        if parent_id:
            parts.append(str(parent_id))
        parts.append(safe_name)

        return os.path.join(*parts)

    async def create_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: bytes,
        filename: str,
        parent_id: str,
        mimetype: str | None = None,
    ):
        """
        Create file in local filesystem.

        Args:
            storage: Storage instance
            attachment: Attachment instance
            content: File content bytes
            filename: Filename
            mimetype: MIME type (not used for local storage)
            parent_id: Parent folder ID (not used for local storage, ignored)

        Returns:
            Dict with storage_file_url
        """
        self._log_operation("create_file", attachment, filename=filename)
        loop = asyncio.get_running_loop()

        # 1. Подготовка данных
        safe_filename = sanitize_filename(os.path.basename(filename))
        checksum = await loop.run_in_executor(
            None, self._compute_checksum, content
        )

        file_path = await self._get_file_path(
            storage, attachment, safe_filename, parent_id, checksum
        )
        dir_path = os.path.dirname(file_path)

        # 2. Создание директорий (синхронно в потоке)
        await loop.run_in_executor(
            None, lambda: os.makedirs(dir_path, exist_ok=True)
        )

        # 3. Асинхронная запись
        async with aiofiles.open(file_path, mode="wb") as f:
            await f.write(content)

        return {
            "storage_file_url": file_path,
            "storage_file_id": None,  # Local storage doesn't use file IDs
            "storage_parent_id": None,
            "storage_parent_name": None,
            "checksum": checksum,
        }

    async def read_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ):
        """
        Read file from local filesystem.

        Args:
            storage: Storage instance
            attachment: Attachment instance

        Returns:
            File content bytes or None if not found
        """
        self._log_operation("read_file", attachment)

        file_path = attachment.storage_file_url
        if not file_path:
            logger.warning(
                "[file] No file path for attachment %s", attachment.id
            )
            return None

        if not await aiofiles.os.path.exists(file_path):
            logger.warning("[file] File not found: %s", file_path)
            return None

        async with aiofiles.open(file_path, mode="rb") as f:
            return await f.read()

    async def update_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: bytes | None = None,
        filename: str | None = None,
        mimetype: str | None = None,
    ) -> dict[str, Any]:
        """
        Update file in local filesystem.

        If content is provided, overwrites the file.
        If filename is provided and different, creates new file and removes old.

        Args:
            storage: Storage instance
            attachment: Attachment instance
            content: New content (optional)
            filename: New filename (optional)
            mimetype: New MIME type (not used)

        Returns:
            Dict with updated storage info
        """
        self._log_operation("update_file", attachment, filename=filename)
        loop = asyncio.get_running_loop()
        result = {}
        old_path = attachment.storage_file_url

        # If content is provided, update the file
        if content:
            checksum = await loop.run_in_executor(
                None, self._compute_checksum, content
            )
            new_filename = sanitize_filename(filename or attachment.name)
            # Build new path
            new_path = await self._get_file_path(
                storage,
                attachment,
                new_filename,
                attachment.storage_parent_id,
                checksum,
            )

            # Создаем папки и записываем
            await loop.run_in_executor(
                None,
                lambda: os.makedirs(os.path.dirname(new_path), exist_ok=True),
            )
            async with aiofiles.open(new_path, mode="wb") as f:
                await f.write(content)

            # Удаляем старый файл, если путь изменился
            if old_path and old_path != new_path:
                try:
                    if await aiofiles.os.path.exists(old_path):
                        await aiofiles.os.remove(old_path)
                        await loop.run_in_executor(
                            None,
                            self._cleanup_empty_dirs,
                            os.path.dirname(old_path),
                        )
                except Exception as e:
                    logger.warning("[file] Cleanup failed: %s", e)

            result.update({"storage_file_url": new_path, "checksum": checksum})

        # If only filename changed (no content), rename
        elif filename and filename != attachment.name and old_path:
            # Только переименование
            new_path = os.path.join(
                os.path.dirname(old_path), sanitize_filename(filename)
            )
            if await aiofiles.os.path.exists(old_path):
                await aiofiles.os.rename(old_path, new_path)
                result["storage_file_url"] = new_path

        return result

    async def delete_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> bool:
        """
        Delete file from local filesystem.

        Args:
            storage: Storage instance
            attachment: Attachment instance

        Returns:
            True if deleted successfully
        """
        self._log_operation("delete_file", attachment)

        file_path = attachment.storage_file_url
        if not file_path:
            return True  # Nothing to delete

        if not await aiofiles.os.path.exists(file_path):
            logger.debug("[file] File already deleted: %s", file_path)
            return True

        try:
            await aiofiles.os.remove(file_path)
            # Очистку пустых папок лучше оставить в executor, так как это рекурсивный системный обход
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, self._cleanup_empty_dirs, os.path.dirname(file_path)
            )
            return True

        except Exception as e:
            logger.error("[file] Delete error: %s", e)
            return False

    def _cleanup_empty_dirs(self, dir_path: str):
        """
        Remove empty directories up to base path.

        Args:
            dir_path: Directory path to start from
        """
        base_path = self._cached_path or self.DEFAULT_FILESTORE_PATH
        try:
            # Используем dir_path как в исходной сигнатуре
            while (
                dir_path
                and dir_path != base_path
                and os.path.isdir(dir_path)
                and not os.listdir(dir_path)
            ):
                os.rmdir(dir_path)
                dir_path = os.path.dirname(dir_path)
        except Exception as e:
            logger.debug("[file] Could not cleanup directories: %s", e)

    async def create_folder(
        self,
        storage: "AttachmentStorage",
        folder_name: str,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Create folder in local filesystem.

        For local storage, folders are created automatically when files are saved.
        This method just returns a path that would be used.

        Args:
            storage: Storage instance
            folder_name: Folder name
            parent_id: Parent folder path (optional)
            metadata: Additional metadata (not used)

        Returns:
            Folder path
        """
        base_path = await self._get_base_path(storage)
        loop = asyncio.get_running_loop()

        # Очищаем имя папки от спецсимволов и путей
        safe_folder_name = sanitize_filename(os.path.basename(folder_name))

        if parent_id:
            # Если parent_id это путь, убеждаемся, что он внутри base_path (опционально, для безопасности)
            folder_path = os.path.join(parent_id, safe_folder_name)
        else:
            folder_path = os.path.join(base_path, safe_folder_name)

        # Создаем директорию асинхронно через executor
        await loop.run_in_executor(
            None, lambda: os.makedirs(folder_path, exist_ok=True)
        )

        logger.debug("[file] Created folder: %s", folder_path)
        return folder_path

    async def validate_connection(self, storage: "AttachmentStorage") -> bool:
        """
        Validate that the storage path is accessible.

        Args:
            storage: Storage instance

        Returns:
            True if path is accessible
        """
        base_path = await self._get_base_path(storage)
        loop = asyncio.get_running_loop()

        try:
            # 1. Проверяем/создаем базовую директорию
            await loop.run_in_executor(
                None, lambda: os.makedirs(base_path, exist_ok=True)
            )

            test_file = os.path.join(base_path, ".test_write")

            # 2. Тестовая запись через aiofiles
            async with aiofiles.open(test_file, mode="w") as f:
                await f.write("test")

            # 3. Удаление через aiofiles.os
            await aiofiles.os.remove(test_file)

            return True
        except Exception as e:
            logger.error("[file] Storage validation failed: %s", e)
            return False
