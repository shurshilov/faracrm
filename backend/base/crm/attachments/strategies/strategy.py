# Copyright 2025 FARA CRM
# Attachments module - base storage strategy

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional
import logging

if TYPE_CHECKING:
    from backend.base.crm.attachments.models.attachments_storage import (
        AttachmentStorage,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)


class StorageStrategyBase(ABC):
    """
    Базовый класс стратегии хранения файлов.

    Реализует паттерн Strategy для легкого добавления новых провайдеров
    хранения (filestore, Google Drive, OneDrive и т.д.) без изменения
    основного кода.

    Каждый провайдер реализует свой класс стратегии, наследуя от этого.

    Attributes:
        strategy_type: Уникальный тип стратегии (должен совпадать с storage.type)
    """

    # Уникальный тип стратегии (должен совпадать с storage.type)
    strategy_type: str = ""

    # ========================================================================
    # Абстрактные методы - должны быть реализованы в каждой стратегии
    # ========================================================================

    @abstractmethod
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
        Создать файл в хранилище.

        Args:
            storage: Экземпляр хранилища
            attachment: Экземпляр вложения (для получения res_model, res_id и т.д.)
            content: Содержимое файла в байтах
            filename: Имя файла
            mimetype: MIME-тип файла
            parent_id: ID родительской папки (для облачных хранилищ)

        Returns:
            Словарь с ключами:
            - storage_file_id: ID файла в хранилище (для облачных)
            - storage_file_url: URL/путь к файлу
            - storage_parent_id: ID родительской папки (для облачных)
            - storage_parent_name: Имя родительской папки
        """
        pass

    @abstractmethod
    async def read_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> Optional[bytes]:
        """
        Прочитать содержимое файла из хранилища.

        Args:
            storage: Экземпляр хранилища
            attachment: Экземпляр вложения

        Returns:
            Содержимое файла в байтах или None если файл не найден
        """
        pass

    @abstractmethod
    async def update_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: Optional[bytes] = None,
        filename: Optional[str] = None,
        mimetype: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Обновить файл в хранилище.

        Args:
            storage: Экземпляр хранилища
            attachment: Экземпляр вложения
            content: Новое содержимое файла (если нужно обновить)
            filename: Новое имя файла (если нужно переименовать)
            mimetype: Новый MIME-тип

        Returns:
            Словарь с обновленными данными хранилища
        """
        pass

    @abstractmethod
    async def delete_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> bool:
        """
        Удалить файл из хранилища.

        Args:
            storage: Экземпляр хранилища
            attachment: Экземпляр вложения

        Returns:
            True если файл успешно удален, иначе False
        """
        pass

    # ========================================================================
    # Опциональные методы - могут быть переопределены в стратегиях
    # ========================================================================

    async def create_folder(
        self,
        storage: "AttachmentStorage",
        folder_name: str,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Создать папку в хранилище (для облачных хранилищ).

        Args:
            storage: Экземпляр хранилища
            folder_name: Имя папки
            parent_id: ID родительской папки
            metadata: Дополнительные метаданные

        Returns:
            ID созданной папки или None если не поддерживается
        """
        logger.debug(
            f"[{self.strategy_type}] create_folder not implemented, returning None"
        )
        return None

    async def get_folder_path(
        self,
        storage: "AttachmentStorage",
        res_model: Optional[str],
        res_id: Optional[int],
        route_id: Optional[int] = None,
    ) -> Optional[str]:
        """
        Получить или создать путь к папке для файла.

        Используется для организации файлов по папкам на основе модели и записи.

        Args:
            storage: Экземпляр хранилища
            res_model: Название модели
            res_id: ID записи
            route_id: ID маршрута (для сложной маршрутизации)

        Returns:
            ID или путь к папке
        """
        return None

    async def get_credentials(
        self, storage: "AttachmentStorage"
    ) -> Optional[Any]:
        """
        Получить или обновить credentials для API.

        Для хранилищ с OAuth или API ключами.

        Args:
            storage: Экземпляр хранилища

        Returns:
            Credentials объект или None
        """
        return None

    async def validate_connection(self, storage: "AttachmentStorage") -> bool:
        """
        Проверить соединение с хранилищем.

        Args:
            storage: Экземпляр хранилища

        Returns:
            True если соединение успешно, иначе False
        """
        return True

    async def get_file_url(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> Optional[str]:
        """
        Получить публичный URL файла для просмотра/скачивания.

        Args:
            storage: Экземпляр хранилища
            attachment: Экземпляр вложения

        Returns:
            URL файла или None
        """
        return attachment.storage_file_url

    async def move_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        new_parent_id: str,
    ) -> Dict[str, Any]:
        """
        Переместить файл в другую папку (для облачных хранилищ).

        Args:
            storage: Экземпляр хранилища
            attachment: Экземпляр вложения
            new_parent_id: ID новой родительской папки

        Returns:
            Словарь с обновленными данными
        """
        raise NotImplementedError(
            f"move_file not supported for {self.strategy_type}"
        )

    # ========================================================================
    # Вспомогательные методы
    # ========================================================================

    def _log_operation(
        self, operation: str, attachment: "Attachment", **kwargs
    ) -> None:
        """Логирование операции."""
        extra = ", ".join(f"{k}={v}" for k, v in kwargs.items() if v)
        logger.debug(
            f"[{self.strategy_type}] {operation}: "
            f"attachment_id={attachment.id}, name={attachment.name}"
            f"{', ' + extra if extra else ''}"
        )

    def _build_file_path(
        self,
        base_path: str,
        res_model: Optional[str],
        res_id: Optional[int],
        filename: str,
    ) -> str:
        """
        Построить путь к файлу.

        Args:
            base_path: Базовый путь хранилища
            res_model: Название модели
            res_id: ID записи
            filename: Имя файла

        Returns:
            Полный путь к файлу
        """
        import os

        parts = [base_path]

        if res_model:
            # Заменяем точки на слеши для модулей (partner.contact -> partner/contact)
            parts.append(res_model.replace(".", "/"))

        if res_id:
            parts.append(str(res_id))

        parts.append(filename)

        return os.path.join(*parts)
