# Copyright 2025 FARA CRM
# Attachments module - FileStore (local filesystem) strategy

import os
import hashlib
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from .strategy import StorageStrategyBase
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.attachments.models.attachments_storage import (
        AttachmentStorage,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)


class FileStoreStrategy(StorageStrategyBase):
    """
    Стратегия хранения файлов в локальной файловой системе.

    Файлы сохраняются в структуре:
        filestore/
        └── <res_model>/
            └── <res_id>/
                └── <checksum_prefix>/<filename>

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
        checksum: Optional[str] = None,
    ) -> str:
        """
        Build file path for storage.

        Structure: filestore/<res_model>/<res_id>/<filename>
        """
        base_path = await self._get_base_path(storage)
        parts = [base_path]

        # Add model folder
        if attachment.res_model:
            parts.append(attachment.res_model.replace(".", "_"))

        # Add record ID folder
        if attachment.res_id:
            parts.append(str(attachment.res_id))

        # Add filename
        parts.append(filename)

        return os.path.join(*parts)

    async def create_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: bytes,
        filename: str,
        mimetype: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
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

        # Compute checksum
        checksum = self._compute_checksum(content)

        # Build file path
        file_path = await self._get_file_path(
            storage, attachment, filename, checksum
        )

        # Create directories
        dir_path = os.path.dirname(file_path)
        os.makedirs(dir_path, exist_ok=True)

        # Write file
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"[file] Created file: {file_path}")

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
    ) -> Optional[bytes]:
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
                f"[file] No file path for attachment {attachment.id}"
            )
            return None

        if not os.path.exists(file_path):
            logger.warning(f"[file] File not found: {file_path}")
            return None

        with open(file_path, "rb") as f:
            return f.read()

    async def update_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: Optional[bytes] = None,
        filename: Optional[str] = None,
        mimetype: Optional[str] = None,
    ) -> Dict[str, Any]:
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

        result = {}
        old_path = attachment.storage_file_url

        # If content is provided, update the file
        if content:
            checksum = self._compute_checksum(content)
            new_filename = filename or attachment.name

            # Build new path
            new_path = await self._get_file_path(
                storage, attachment, new_filename, checksum
            )

            # Create directories
            dir_path = os.path.dirname(new_path)
            os.makedirs(dir_path, exist_ok=True)

            # Write new file
            with open(new_path, "wb") as f:
                f.write(content)

            # Remove old file if path changed
            if old_path and old_path != new_path and os.path.exists(old_path):
                try:
                    os.remove(old_path)
                    # Try to remove empty parent directories
                    self._cleanup_empty_dirs(os.path.dirname(old_path))
                except Exception as e:
                    logger.warning(f"[file] Failed to remove old file: {e}")

            result["storage_file_url"] = new_path
            result["checksum"] = checksum

        # If only filename changed (no content), rename
        elif filename and filename != attachment.name and old_path:
            new_path = os.path.join(os.path.dirname(old_path), filename)

            if os.path.exists(old_path):
                os.rename(old_path, new_path)
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

        if not os.path.exists(file_path):
            logger.debug(f"[file] File already deleted: {file_path}")
            return True

        try:
            os.remove(file_path)

            # Try to remove empty parent directories
            self._cleanup_empty_dirs(os.path.dirname(file_path))

            logger.info(f"[file] Deleted file: {file_path}")
            return True

        except Exception as e:
            logger.error(f"[file] Failed to delete file {file_path}: {e}")
            return False

    def _cleanup_empty_dirs(self, dir_path: str) -> None:
        """
        Remove empty directories up to base path.

        Args:
            dir_path: Directory path to start from
        """
        base_path = self._cached_path or self.DEFAULT_FILESTORE_PATH
        try:
            while dir_path and dir_path != base_path:
                if os.path.isdir(dir_path) and not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    dir_path = os.path.dirname(dir_path)
                else:
                    break
        except Exception as e:
            logger.debug(f"[file] Could not cleanup directories: {e}")

    async def create_folder(
        self,
        storage: "AttachmentStorage",
        folder_name: str,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
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

        if parent_id:
            folder_path = os.path.join(parent_id, folder_name)
        else:
            folder_path = os.path.join(base_path, folder_name)

        # Create the directory
        os.makedirs(folder_path, exist_ok=True)

        logger.debug(f"[file] Created folder: {folder_path}")
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

        try:
            os.makedirs(base_path, exist_ok=True)
            # Test write access
            test_file = os.path.join(base_path, ".test_write")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except Exception as e:
            logger.error(f"[file] Storage validation failed: {e}")
            return False
