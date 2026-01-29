# Copyright 2025 FARA CRM
# Attachments module - FileStore storage strategy

import os
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from backend.base.crm.attachments.strategies.strategy import (
    StorageStrategyBase,
)
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.attachments.models.attachments_storage import (
        AttachmentStorage,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)


class FileStoreStrategy(StorageStrategyBase):
    """
    Стратегия локального хранения файлов в файловой системе.

    Файлы сохраняются в директории, указанной в настройках:
    {filestore_path}/{res_model}/{res_id}/{filename}

    Это стратегия по умолчанию, которая регистрируется автоматически.
    """

    strategy_type = "file"

    def _get_filestore_path(self) -> str:
        """Получить базовый путь хранилища."""
        try:
            return env.settings.attachments.filestore_path
        except AttributeError:
            # Fallback если настройки не заданы
            default_path = os.path.join(os.getcwd(), "filestore")
            logger.warning(
                f"filestore_path not configured, using default: {default_path}"
            )
            return default_path

    def _build_storage_path(
        self,
        res_model: Optional[str],
        res_id: Optional[int],
        filename: str,
    ) -> str:
        """
        Построить полный путь к файлу в хранилище.

        Args:
            res_model: Название модели
            res_id: ID записи
            filename: Имя файла

        Returns:
            Полный путь к файлу
        """
        base_path = self._get_filestore_path()
        return self._build_file_path(base_path, res_model, res_id, filename)

    async def create_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: bytes,
        filename: str,
        mimetype: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Создать файл в локальном хранилище.

        Args:
            storage: Экземпляр хранилища
            attachment: Экземпляр вложения
            content: Содержимое файла
            filename: Имя файла
            mimetype: MIME-тип (не используется для filestore)

        Returns:
            Словарь с storage_file_url
        """
        file_path = self._build_storage_path(
            attachment.res_model,
            attachment.res_id,
            filename,
        )

        self._log_operation("create_file", attachment, path=file_path)

        try:
            # Создаем директорию если не существует
            dir_path = os.path.dirname(file_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.debug(f"Created directory: {dir_path}")

            # Записываем файл
            with open(file_path, "wb") as f:
                f.write(content)

            logger.info(f"File created: {file_path} ({len(content)} bytes)")

            return {
                "storage_file_url": file_path,
                "storage_file_id": None,
                "storage_parent_id": None,
                "storage_parent_name": None,
            }

        except IOError as e:
            logger.error(f"Failed to create file {file_path}: {e}")
            raise

    async def read_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> Optional[bytes]:
        """
        Прочитать файл из локального хранилища.

        Args:
            storage: Экземпляр хранилища
            attachment: Экземпляр вложения

        Returns:
            Содержимое файла или None
        """
        file_path = attachment.storage_file_url

        if not file_path:
            logger.warning(
                f"No storage_file_url for attachment {attachment.id}"
            )
            return None

        self._log_operation("read_file", attachment, path=file_path)

        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return None

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            logger.debug(f"File read: {file_path} ({len(content)} bytes)")
            return content

        except IOError as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None

    async def update_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: Optional[bytes] = None,
        filename: Optional[str] = None,
        mimetype: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Обновить файл в локальном хранилище.

        Args:
            storage: Экземпляр хранилища
            attachment: Экземпляр вложения
            content: Новое содержимое
            filename: Новое имя файла

        Returns:
            Словарь с обновленным storage_file_url
        """
        current_path = attachment.storage_file_url
        new_path = current_path

        self._log_operation(
            "update_file",
            attachment,
            path=current_path,
            new_filename=filename,
        )

        try:
            # Если меняется имя файла - переименовываем
            if filename and filename != attachment.name:
                new_path = self._build_storage_path(
                    attachment.res_model,
                    attachment.res_id,
                    filename,
                )

                # Создаем новую директорию если нужно
                new_dir = os.path.dirname(new_path)
                if not os.path.exists(new_dir):
                    os.makedirs(new_dir, exist_ok=True)

                # Перемещаем файл
                if current_path and os.path.exists(current_path):
                    os.rename(current_path, new_path)
                    logger.info(f"File renamed: {current_path} -> {new_path}")

            # Если есть новое содержимое - записываем
            if content:
                target_path = new_path or current_path
                if target_path:
                    with open(target_path, "wb") as f:
                        f.write(content)
                    logger.info(
                        f"File updated: {target_path} ({len(content)} bytes)"
                    )

            return {
                "storage_file_url": new_path,
            }

        except IOError as e:
            logger.error(f"Failed to update file: {e}")
            raise

    async def delete_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> bool:
        """
        Удалить файл из локального хранилища.

        Args:
            storage: Экземпляр хранилища
            attachment: Экземпляр вложения

        Returns:
            True если файл удален
        """
        file_path = attachment.storage_file_url

        if not file_path:
            logger.warning(
                f"No storage_file_url for attachment {attachment.id}"
            )
            return False

        self._log_operation("delete_file", attachment, path=file_path)

        if not os.path.exists(file_path):
            logger.warning(f"File not found for deletion: {file_path}")
            return False

        try:
            os.remove(file_path)
            logger.info(f"File deleted: {file_path}")

            # Попытаемся удалить пустые родительские директории
            self._cleanup_empty_dirs(os.path.dirname(file_path))

            return True

        except IOError as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    def _cleanup_empty_dirs(self, dir_path: str) -> None:
        """
        Удалить пустые родительские директории.

        Args:
            dir_path: Путь к директории
        """
        base_path = self._get_filestore_path()

        try:
            while dir_path and dir_path != base_path:
                if os.path.isdir(dir_path) and not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    logger.debug(f"Removed empty directory: {dir_path}")
                    dir_path = os.path.dirname(dir_path)
                else:
                    break
        except OSError:
            # Игнорируем ошибки при удалении директорий
            pass

    async def validate_connection(self, storage: "AttachmentStorage") -> bool:
        """
        Проверить доступность filestore.

        Returns:
            True если директория доступна для записи
        """
        base_path = self._get_filestore_path()

        try:
            # Проверяем что можем создать директорию
            if not os.path.exists(base_path):
                os.makedirs(base_path, exist_ok=True)

            # Проверяем права на запись
            test_file = os.path.join(base_path, ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)

            return True

        except (IOError, OSError) as e:
            logger.error(f"FileStore validation failed: {e}")
            return False

    async def get_file_url(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> Optional[str]:
        """
        Для filestore возвращает локальный путь.

        В реальном приложении может потребоваться преобразование
        в URL через web-сервер.
        """
        return attachment.storage_file_url
