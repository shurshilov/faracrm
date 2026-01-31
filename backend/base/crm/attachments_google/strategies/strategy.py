# Copyright 2025 FARA CRM
# Attachments Google Drive module - storage strategy

from datetime import datetime, timezone, timedelta
import io
import json
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from backend.base.crm.attachments.strategies.strategy import (
    StorageStrategyBase,
)

if TYPE_CHECKING:
    from backend.project_setup import (
        AttachmentStorage,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)

# Google API scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleDriveStrategy(StorageStrategyBase):
    """
    Стратегия хранения файлов в Google Drive.

    Поддерживает:
    - Создание, чтение, обновление, удаление файлов
    - Создание папок
    - My Drive и Shared Drives (Team Drives)
    - OAuth2 авторизация

    Требует установки пакетов:
    - google-auth
    - google-auth-oauthlib
    - google-api-python-client
    """

    strategy_type = "google"

    # URL для просмотра папок в Google Drive
    folder_url = "https://drive.google.com/drive/folders/"
    file_url = "https://drive.google.com/file/d/"

    async def _get_service(self, storage: "AttachmentStorage"):
        """
        Создать Google Drive API service.

        Args:
            storage: Хранилище с credentials

        Returns:
            Google Drive API service object

        Raises:
            ValueError: Если credentials не настроены
        """
        import google.oauth2.credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        if not storage.google_credentials:
            raise ValueError(
                f"Google Drive credentials not configured for storage {storage.id}"
            )

        try:
            credentials_data = json.loads(storage.google_credentials)

            # Извлекаем expiry отдельно (не передаём в Credentials)
            expiry_value = credentials_data.pop("expiry", None)

            credentials = google.oauth2.credentials.Credentials(
                **credentials_data
            )

            # Проверяем нужно ли обновить токен
            needs_refresh = False
            now = datetime.now(timezone.utc)

            if expiry_value is None:
                needs_refresh = True
                logger.debug("Token expiry unknown, refreshing")
            else:
                # Парсим expiry (может быть timestamp или ISO строка)
                expiry = datetime.fromisoformat(
                    expiry_value.replace("Z", "+00:00")
                )

                if expiry <= now:
                    needs_refresh = True
                    logger.debug("Token expired")
                elif expiry < now + timedelta(minutes=5):
                    needs_refresh = True
                    logger.debug("Token expires soon, refreshing preventively")

            if needs_refresh and credentials.refresh_token:
                logger.debug("Refreshing access token...")
                credentials.refresh(Request())

                # Сохраняем обновлённые credentials обратно в storage
                await self._save_refreshed_credentials(storage, credentials)

            return build("drive", "v3", credentials=credentials)
        except Exception as e:
            logger.error(f"Failed to create Google Drive service: {e}")
            raise ValueError(f"Invalid Google credentials: {e}") from e

    async def _save_refreshed_credentials(
        self,
        storage: "AttachmentStorage",
        credentials,
    ) -> None:
        """
        Сохранить обновлённые credentials в storage.

        Args:
            storage: Хранилище
            credentials: Обновлённые Google credentials
        """
        from backend.base.system.core.enviroment import env

        # Обновляем в памяти
        storage.google_credentials = credentials.to_json()

        # Асинхронно сохраняем в БД
        updated_storage = env.models.attachment_storage()
        updated_storage.google_credentials = credentials.to_json()
        await storage.update(
            updated_storage,
        )
        logger.debug(f"Refreshed credentials saved to storage {storage.id}")

    def _get_parent_id(self, storage: "AttachmentStorage") -> Optional[str]:
        """
        Получить ID родительской папки для файлов.

        Args:
            storage: Хранилище

        Returns:
            ID папки или None для корня My Drive
        """
        # Приоритет: team drive -> folder_id -> None (root)
        if storage.google_team_enabled and storage.google_team_id:
            return storage.google_team_id
        return storage.google_folder_id

    async def create_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: bytes,
        filename: str,
        mimetype: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Создать файл в Google Drive.

        Args:
            storage: Хранилище
            attachment: Вложение
            content: Содержимое файла
            filename: Имя файла
            mimetype: MIME-тип

        Returns:
            Словарь с storage_file_id, storage_file_url, etc.
        """
        from googleapiclient.http import MediaIoBaseUpload

        self._log_operation("create_file", attachment, filename=filename)

        service = await self._get_service(storage)

        # Метаданные файла
        file_metadata = {"name": filename}

        # Устанавливаем родительскую папку
        parent_id = self._get_parent_id(storage)
        if parent_id:
            file_metadata["parents"] = [parent_id]

        # Для Shared Drive
        if storage.google_team_enabled and storage.google_team_id:
            file_metadata["driveId"] = storage.google_team_id

        # Загружаем файл
        media = MediaIoBaseUpload(
            io.BytesIO(content),
            mimetype=mimetype or "application/octet-stream",
            resumable=True,
        )

        try:
            file = (
                service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, webViewLink, parents",
                    supportsTeamDrives=storage.google_team_enabled or None,
                )
                .execute()
            )

            logger.info(
                f"File created in Google Drive: {file.get('id')} - {filename}"
            )

            return {
                "storage_file_id": file.get("id"),
                "storage_file_url": file.get("webViewLink"),
                "storage_parent_id": parent_id,
                "storage_parent_name": None,  # Можно получить отдельным запросом
            }

        except Exception as e:
            logger.error(f"Failed to create file in Google Drive: {e}")
            raise

    async def read_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> Optional[bytes]:
        """
        Прочитать файл из Google Drive.

        Args:
            storage: Хранилище
            attachment: Вложение

        Returns:
            Содержимое файла или None
        """
        from googleapiclient.http import MediaIoBaseDownload

        if not attachment.storage_file_id:
            logger.warning(
                f"No storage_file_id for attachment {attachment.id}"
            )
            return None

        self._log_operation(
            "read_file", attachment, file_id=attachment.storage_file_id
        )

        service = await self._get_service(storage)

        try:
            request = service.files().get_media(
                fileId=attachment.storage_file_id,
                supportsTeamDrives=storage.google_team_enabled or None,
            )

            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(
                        f"Download progress: {int(status.progress() * 100)}%"
                    )

            content = buffer.getvalue()
            logger.debug(
                f"File downloaded from Google Drive: {len(content)} bytes"
            )
            return content

        except Exception as e:
            logger.error(
                f"Failed to read file {attachment.storage_file_id} "
                f"from Google Drive: {e}"
            )
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
        Обновить файл в Google Drive.

        Args:
            storage: Хранилище
            attachment: Вложение
            content: Новое содержимое
            filename: Новое имя
            mimetype: Новый MIME-тип

        Returns:
            Словарь с обновленными данными
        """
        from googleapiclient.http import MediaIoBaseUpload

        if not attachment.storage_file_id:
            raise ValueError(
                f"No storage_file_id for attachment {attachment.id}"
            )

        self._log_operation(
            "update_file",
            attachment,
            file_id=attachment.storage_file_id,
            new_filename=filename,
        )

        service = await self._get_service(storage)

        try:
            file_metadata = {}
            if filename:
                file_metadata["name"] = filename

            if content:
                media = MediaIoBaseUpload(
                    io.BytesIO(content),
                    mimetype=mimetype
                    or attachment.mimetype
                    or "application/octet-stream",
                    resumable=True,
                )

                if file_metadata:
                    service.files().update(
                        fileId=attachment.storage_file_id,
                        body=file_metadata,
                        media_body=media,
                        supportsTeamDrives=storage.google_team_enabled or None,
                    ).execute()
                else:
                    service.files().update(
                        fileId=attachment.storage_file_id,
                        media_body=media,
                        supportsTeamDrives=storage.google_team_enabled or None,
                    ).execute()
            elif file_metadata:
                service.files().update(
                    fileId=attachment.storage_file_id,
                    body=file_metadata,
                    supportsTeamDrives=storage.google_team_enabled or None,
                ).execute()

            logger.info(
                f"File updated in Google Drive: {attachment.storage_file_id}"
            )

            return {
                "storage_file_id": attachment.storage_file_id,
            }

        except Exception as e:
            logger.error(
                f"Failed to update file {attachment.storage_file_id} "
                f"in Google Drive: {e}"
            )
            raise

    async def delete_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> bool:
        """
        Удалить файл из Google Drive.

        Args:
            storage: Хранилище
            attachment: Вложение

        Returns:
            True если файл удален
        """
        if not attachment.storage_file_id:
            logger.warning(
                f"No storage_file_id for attachment {attachment.id}"
            )
            return False

        self._log_operation(
            "delete_file", attachment, file_id=attachment.storage_file_id
        )

        service = await self._get_service(storage)

        try:
            service.files().delete(
                fileId=attachment.storage_file_id,
                supportsTeamDrives=storage.google_team_enabled or None,
            ).execute()

            logger.info(
                f"File deleted from Google Drive: {attachment.storage_file_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to delete file {attachment.storage_file_id} "
                f"from Google Drive: {e}"
            )
            return False

    async def create_folder(
        self,
        storage: "AttachmentStorage",
        folder_name: str,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Создать папку в Google Drive.

        Если папка с таким именем уже существует в parent - возвращает её ID.

        Args:
            storage: Хранилище
            folder_name: Имя папки
            parent_id: ID родительской папки
            metadata: Дополнительные метаданные (properties)

        Returns:
            ID созданной/существующей папки
        """
        logger.debug(
            f"[google] create_folder: {folder_name}, parent={parent_id}"
        )

        service = await self._get_service(storage)

        # Определяем родителя
        if not parent_id:
            parent_id = self._get_parent_id(storage)

        try:
            # Экранируем спецсимволы в имени
            escaped_name = folder_name.replace("\\", "\\\\").replace(
                "'", r"\'"
            )

            # Проверяем существует ли уже такая папка
            query = (
                f"mimeType='application/vnd.google-apps.folder' "
                f"and trashed=false and name='{escaped_name}'"
            )
            if parent_id:
                query += f" and parents='{parent_id}'"

            response = (
                service.files()
                .list(
                    q=query,
                    supportsAllDrives=storage.google_team_enabled or None,
                    supportsTeamDrives=storage.google_team_enabled or None,
                    includeTeamDriveItems=storage.google_team_enabled or None,
                    includeItemsFromAllDrives=storage.google_team_enabled
                    or None,
                    corpora=(
                        "allDrives" if storage.google_team_enabled else "user"
                    ),
                )
                .execute()
            )

            # Если папка существует - возвращаем её ID
            if response.get("files"):
                folder_id = response["files"][0].get("id")
                logger.debug(f"Folder already exists: {folder_id}")
                return folder_id

            # Создаем новую папку
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }

            if parent_id:
                file_metadata["parents"] = [parent_id]

            if metadata:
                file_metadata["properties"] = metadata

            if storage.google_team_enabled and storage.google_team_id:
                file_metadata["driveId"] = storage.google_team_id

            folder = (
                service.files()
                .create(
                    body=file_metadata,
                    fields="id",
                    supportsTeamDrives=storage.google_team_enabled or None,
                )
                .execute()
            )

            folder_id = folder.get("id")
            logger.info(f"Folder created in Google Drive: {folder_id}")
            return folder_id

        except Exception as e:
            logger.error(f"Failed to create folder in Google Drive: {e}")
            return None

    async def validate_connection(self, storage: "AttachmentStorage") -> bool:
        """
        Проверить подключение к Google Drive.

        Args:
            storage: Хранилище

        Returns:
            True если подключение успешно
        """
        if not storage.google_credentials:
            return False

        try:
            service = await self._get_service(storage)

            # Пробуем получить информацию о пользователе
            about = service.about().get(fields="user").execute()

            logger.info(
                f"Google Drive connected as: "
                f"{about.get('user', {}).get('emailAddress')}"
            )
            return True

        except Exception as e:
            logger.error(f"Google Drive connection failed: {e}")
            return False

    async def get_file_url(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> Optional[str]:
        """
        Получить URL файла в Google Drive.

        Args:
            storage: Хранилище
            attachment: Вложение

        Returns:
            URL для просмотра файла
        """
        if attachment.storage_file_url:
            return attachment.storage_file_url

        if attachment.storage_file_id:
            return f"{self.file_url}{attachment.storage_file_id}/view"

        return None

    async def move_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        new_parent_id: str,
    ) -> Dict[str, Any]:
        """
        Переместить файл в другую папку.

        Args:
            storage: Хранилище
            attachment: Вложение
            new_parent_id: ID новой родительской папки

        Returns:
            Словарь с обновленными данными
        """
        if not attachment.storage_file_id:
            raise ValueError(
                f"No storage_file_id for attachment {attachment.id}"
            )

        self._log_operation(
            "move_file",
            attachment,
            file_id=attachment.storage_file_id,
            new_parent=new_parent_id,
        )

        service = await self._get_service(storage)

        try:
            # Получаем текущих родителей
            file = (
                service.files()
                .get(
                    fileId=attachment.storage_file_id,
                    fields="parents",
                    supportsTeamDrives=storage.google_team_enabled or None,
                )
                .execute()
            )

            current_parents = ",".join(file.get("parents", []))

            # Перемещаем файл
            updated_file = (
                service.files()
                .update(
                    fileId=attachment.storage_file_id,
                    addParents=new_parent_id,
                    removeParents=current_parents,
                    fields="id, parents",
                    supportsTeamDrives=storage.google_team_enabled or None,
                )
                .execute()
            )

            logger.info(
                f"File moved in Google Drive: {attachment.storage_file_id} "
                f"-> {new_parent_id}"
            )

            return {
                "storage_parent_id": new_parent_id,
            }

        except Exception as e:
            logger.error(
                f"Failed to move file {attachment.storage_file_id}: {e}"
            )
            raise
