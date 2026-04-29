# Copyright 2025 FARA CRM
# Attachments Yandex Disk module - storage strategy

from datetime import datetime, timezone, timedelta
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx

from backend.base.crm.attachments.strategies.strategy import (
    StorageStrategyBase,
)

if TYPE_CHECKING:
    from backend.project_setup import (
        AttachmentStorage,
    )
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)

# Базовые URL Яндекс.Диск REST API
DISK_API_BASE = "https://cloud-api.yandex.net/v1/disk"
OAUTH_TOKEN_URL = "https://oauth.yandex.ru/token"

# URL для просмотра файлов/папок в веб-интерфейсе Яндекс.Диска
WEB_DISK_BASE = "https://disk.yandex.ru/client/disk"

# Таймаут HTTP-запросов (секунды)
HTTP_TIMEOUT = 60.0


class YandexDiskStrategy(StorageStrategyBase):
    """
    Стратегия хранения файлов в Яндекс.Диске.

    Поддерживает:
    - Создание, чтение, обновление, удаление файлов
    - Создание папок
    - OAuth2 авторизация с автоматическим обновлением access token

    В Яндекс.Диске нет ID-ов ресурсов в стиле Google Drive: ресурс
    идентифицируется его путём. Поэтому в attachment.storage_file_id
    хранится полный путь к файлу (например, "/CRM/lead_42/photo.jpg"),
    а в storage_parent_id — путь к папке.
    """

    strategy_type = "yandex"

    file_url_base = WEB_DISK_BASE

    # ------------------------------------------------------------------ #
    # Вспомогательные методы
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize_path(path: str | None) -> str:
        """
        Привести путь к виду, ожидаемому API: "/" в начале, без хвостового "/".

        "" -> "/"
        "CRM" -> "/CRM"
        "/CRM/" -> "/CRM"
        "/" -> "/"
        """
        if not path:
            return "/"
        path = path.strip()
        if not path.startswith("/") and not path.startswith("app:/"):
            path = "/" + path
        # Убираем хвостовой "/", если он не единственный
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        return path

    @classmethod
    def _join_path(cls, parent: str | None, name: str) -> str:
        """Соединить путь к папке и имя файла/папки."""
        parent = cls._normalize_path(parent)
        name = name.strip("/")
        if parent == "/":
            return f"/{name}"
        return f"{parent}/{name}"

    def _get_root_path(self, storage: "AttachmentStorage") -> str:
        """Получить путь к корневой папке хранилища."""
        return self._normalize_path(
            getattr(storage, "yandex_folder_path", None)
        )

    async def _ensure_token(self, storage: "AttachmentStorage") -> str:
        """
        Получить актуальный access_token, при необходимости обновив его.

        Returns:
            Действующий access token.

        Raises:
            ValueError: Если хранилище не авторизовано.
        """
        if not storage.yandex_access_token:
            raise ValueError(
                f"Yandex Disk credentials not configured for storage {storage.id}"
            )

        # Проверяем срок действия токена
        needs_refresh = False
        now = datetime.now(timezone.utc)
        expires_at_raw = storage.yandex_token_expires_at

        if not expires_at_raw:
            needs_refresh = True
            logger.debug("Yandex token expiry unknown, refreshing")
        else:
            try:
                expires_at = datetime.fromisoformat(
                    expires_at_raw.replace("Z", "+00:00")
                )
                if expires_at <= now:
                    needs_refresh = True
                    logger.debug("Yandex token expired")
                elif expires_at < now + timedelta(minutes=5):
                    needs_refresh = True
                    logger.debug(
                        "Yandex token expires soon, refreshing preventively"
                    )
            except (ValueError, AttributeError) as e:
                logger.warning("Cannot parse yandex_token_expires_at: %s", e)
                needs_refresh = True

        if needs_refresh and storage.yandex_refresh_token:
            await self._refresh_access_token(storage)

        return storage.yandex_access_token

    async def _refresh_access_token(
        self, storage: "AttachmentStorage"
    ) -> None:
        """
        Обновить access_token через refresh_token и сохранить в storage.
        """
        from backend.base.system.core.enviroment import env

        if not (
            storage.yandex_refresh_token
            and storage.yandex_client_id
            and storage.yandex_client_secret
        ):
            raise ValueError(
                "Cannot refresh Yandex token: missing client credentials "
                f"or refresh token for storage {storage.id}"
            )

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(
                OAUTH_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": storage.yandex_refresh_token,
                    "client_id": storage.yandex_client_id,
                    "client_secret": storage.yandex_client_secret,
                },
            )

        if response.status_code != 200:
            logger.error(
                "Failed to refresh Yandex token: %s %s",
                response.status_code,
                response.text,
            )
            raise ValueError(
                f"Yandex token refresh failed: {response.status_code}"
            )

        data = response.json()
        access_token = data.get("access_token")
        refresh_token = (
            data.get("refresh_token") or storage.yandex_refresh_token
        )
        expires_in = int(data.get("expires_in", 0) or 0)

        if not access_token:
            raise ValueError(
                "Yandex token response did not contain access_token"
            )

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Обновляем в памяти
        storage.yandex_access_token = access_token
        storage.yandex_refresh_token = refresh_token
        storage.yandex_token_expires_at = expires_at.isoformat()

        # Асинхронно сохраняем в БД
        updated_storage = env.models.attachment_storage()
        updated_storage.yandex_access_token = access_token
        updated_storage.yandex_refresh_token = refresh_token
        updated_storage.yandex_token_expires_at = expires_at.isoformat()
        await storage.update(updated_storage)

        logger.debug("Refreshed Yandex token saved to storage %s", storage.id)

    async def _request(
        self,
        storage: "AttachmentStorage",
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        """Выполнить авторизованный запрос к API Яндекс.Диска."""
        token = await self._ensure_token(storage)
        request_headers = {"Authorization": f"OAuth {token}"}
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json,
                headers=request_headers,
                content=content,
            )
        return response

    async def _ensure_folder_exists(
        self,
        storage: "AttachmentStorage",
        path: str,
    ) -> bool:
        """
        Убедиться, что папка по указанному пути существует.

        Если её нет — создаёт всю цепочку отсутствующих родительских папок.
        Корень "/" и app:/ считаются существующими по умолчанию.

        Returns:
            True если папка существует/создана, иначе False.
        """
        normalized = self._normalize_path(path)
        if normalized in ("/", "app:/", "app:"):
            return True

        # Делим путь на сегменты и создаём по очереди.
        # Префикс "app:" остаётся как есть.
        if normalized.startswith("app:/"):
            prefix = "app:"
            tail = normalized[len("app:") :]  # начинается с "/"
        else:
            prefix = ""
            tail = normalized

        segments = [s for s in tail.split("/") if s]
        current = prefix or ""

        for segment in segments:
            current = f"{current}/{segment}" if current else f"/{segment}"
            response = await self._request(
                storage,
                "PUT",
                f"{DISK_API_BASE}/resources",
                params={"path": current},
            )
            # 201 — создана; 409 — уже существует; 404 у родителя быть
            # не должно, так как мы поднимаемся постепенно.
            if response.status_code not in (201, 409):
                logger.error(
                    "Failed to ensure Yandex folder %s: %s %s",
                    current,
                    response.status_code,
                    response.text,
                )
                return False

        return True

    # ------------------------------------------------------------------ #
    # Реализация методов StorageStrategyBase
    # ------------------------------------------------------------------ #

    async def create_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: bytes,
        filename: str,
        mimetype: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Загрузить файл в Яндекс.Диск.

        В Яндекс.Диск загрузка двухшаговая:
        1) GET /resources/upload?path=...&overwrite=true → получаем upload-URL.
        2) PUT на upload-URL с телом файла (без авторизации).
        """
        self._log_operation("create_file", attachment, filename=filename)

        parent_path = parent_id or self._get_root_path(storage)
        file_path = self._join_path(parent_path, filename)

        # Гарантируем, что папка-получатель существует
        await self._ensure_folder_exists(storage, parent_path)

        # 1. Получаем URL для загрузки
        upload_resp = await self._request(
            storage,
            "GET",
            f"{DISK_API_BASE}/resources/upload",
            params={"path": file_path, "overwrite": "true"},
        )

        if upload_resp.status_code != 200:
            logger.error(
                "Failed to get Yandex upload URL: %s %s",
                upload_resp.status_code,
                upload_resp.text,
            )
            upload_resp.raise_for_status()

        upload_data = upload_resp.json()
        upload_href = upload_data.get("href")
        upload_method = (upload_data.get("method") or "PUT").upper()

        if not upload_href:
            raise ValueError("Yandex API did not return upload URL")

        # 2. Загружаем содержимое (по этому URL OAuth токен не требуется)
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            put_resp = await client.request(
                upload_method,
                upload_href,
                content=content,
                headers={
                    "Content-Type": mimetype or "application/octet-stream",
                },
            )

        if put_resp.status_code not in (200, 201, 202):
            logger.error(
                "Failed to upload file to Yandex Disk: %s %s",
                put_resp.status_code,
                put_resp.text,
            )
            put_resp.raise_for_status()

        logger.info("File uploaded to Yandex Disk: %s", file_path)

        # Веб-URL: открывает родительскую папку с предпросмотром файла
        web_url = self._build_web_url(file_path)

        return {
            "storage_file_id": file_path,
            "storage_file_url": web_url,
            "storage_parent_id": parent_path,
            "storage_parent_name": None,
        }

    async def read_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> bytes | None:
        """
        Скачать файл с Яндекс.Диска.

        Двухшаговое: получить download-URL, затем GET по нему.
        """
        if not attachment.storage_file_id:
            logger.warning(
                "No storage_file_id for attachment %s", attachment.id
            )
            return None

        self._log_operation(
            "read_file", attachment, file_id=attachment.storage_file_id
        )

        try:
            # 1. Получаем download URL
            dl_resp = await self._request(
                storage,
                "GET",
                f"{DISK_API_BASE}/resources/download",
                params={"path": attachment.storage_file_id},
            )

            if dl_resp.status_code != 200:
                logger.error(
                    "Failed to get Yandex download URL for %s: %s %s",
                    attachment.storage_file_id,
                    dl_resp.status_code,
                    dl_resp.text,
                )
                return None

            href = dl_resp.json().get("href")
            if not href:
                logger.error(
                    "Yandex API did not return download URL for %s",
                    attachment.storage_file_id,
                )
                return None

            # 2. Скачиваем содержимое (по этому URL OAuth не требуется)
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT, follow_redirects=True
            ) as client:
                file_resp = await client.get(href)

            if file_resp.status_code != 200:
                logger.error(
                    "Failed to download file from Yandex Disk: %s",
                    file_resp.status_code,
                )
                return None

            content = file_resp.content
            logger.debug(
                "File downloaded from Yandex Disk: %s bytes", len(content)
            )
            return content

        except Exception as e:
            logger.error(
                "Failed to read file %s from Yandex Disk: %s",
                attachment.storage_file_id,
                e,
            )
            return None

    async def update_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: bytes | None = None,
        filename: str | None = None,
        mimetype: str | None = None,
    ) -> dict[str, Any]:
        """
        Обновить файл в Яндекс.Диске.

        Может включать перезапись содержимого и/или переименование.
        """
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

        current_path = attachment.storage_file_id
        new_path = current_path

        # Если меняется имя — сначала переименуем (move в той же папке)
        if filename:
            parent = current_path.rsplit("/", 1)[0] or "/"
            new_path = self._join_path(parent, filename)
            if new_path != current_path:
                move_resp = await self._request(
                    storage,
                    "POST",
                    f"{DISK_API_BASE}/resources/move",
                    params={
                        "from": current_path,
                        "path": new_path,
                        "overwrite": "true",
                    },
                )
                if move_resp.status_code not in (200, 201, 202):
                    logger.error(
                        "Failed to rename Yandex file %s -> %s: %s %s",
                        current_path,
                        new_path,
                        move_resp.status_code,
                        move_resp.text,
                    )
                    move_resp.raise_for_status()
                logger.info(
                    "Renamed Yandex file: %s -> %s", current_path, new_path
                )

        # Если меняется содержимое — перезапись через upload URL
        if content is not None:
            upload_resp = await self._request(
                storage,
                "GET",
                f"{DISK_API_BASE}/resources/upload",
                params={"path": new_path, "overwrite": "true"},
            )
            if upload_resp.status_code != 200:
                logger.error(
                    "Failed to get upload URL for %s: %s %s",
                    new_path,
                    upload_resp.status_code,
                    upload_resp.text,
                )
                upload_resp.raise_for_status()

            upload_data = upload_resp.json()
            href = upload_data.get("href")
            method = (upload_data.get("method") or "PUT").upper()

            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                put_resp = await client.request(
                    method,
                    href,
                    content=content,
                    headers={
                        "Content-Type": mimetype
                        or attachment.mimetype
                        or "application/octet-stream",
                    },
                )

            if put_resp.status_code not in (200, 201, 202):
                logger.error(
                    "Failed to upload updated file to Yandex Disk: %s %s",
                    put_resp.status_code,
                    put_resp.text,
                )
                put_resp.raise_for_status()

        logger.info("File updated in Yandex Disk: %s", new_path)

        return {
            "storage_file_id": new_path,
            "storage_file_url": self._build_web_url(new_path),
        }

    async def delete_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> bool:
        """Удалить файл (без помещения в корзину) с Яндекс.Диска."""
        if not attachment.storage_file_id:
            logger.warning(
                "No storage_file_id for attachment %s", attachment.id
            )
            return False

        self._log_operation(
            "delete_file", attachment, file_id=attachment.storage_file_id
        )

        try:
            response = await self._request(
                storage,
                "DELETE",
                f"{DISK_API_BASE}/resources",
                params={
                    "path": attachment.storage_file_id,
                    "permanently": "true",
                },
            )

            # 204 No Content — файл удалён, 202 Accepted — асинхронное удаление
            if response.status_code in (202, 204):
                logger.info(
                    "File deleted from Yandex Disk: %s",
                    attachment.storage_file_id,
                )
                return True

            # 404 — уже отсутствует, считаем успешным удалением
            if response.status_code == 404:
                logger.warning(
                    "Yandex file not found on delete (already gone?): %s",
                    attachment.storage_file_id,
                )
                return True

            logger.error(
                "Failed to delete Yandex file %s: %s %s",
                attachment.storage_file_id,
                response.status_code,
                response.text,
            )
            return False

        except Exception as e:
            logger.error(
                "Failed to delete file %s from Yandex Disk: %s",
                attachment.storage_file_id,
                e,
            )
            return False

    async def create_folder(
        self,
        storage: "AttachmentStorage",
        folder_name: str,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Создать папку в Яндекс.Диске.

        Если папка уже существует — возвращает её путь.

        В Яндекс.Диске папка создаётся PUT /resources?path=...
        Возвращаемое "ID" — это путь.
        """
        logger.debug(
            "[yandex] create_folder: %s, parent=%s", folder_name, parent_id
        )

        parent_path = parent_id or self._get_root_path(storage)
        folder_path = self._join_path(parent_path, folder_name)

        try:
            # Если родительской иерархии нет — создаём её.
            # Сама целевая папка также будет создана внутри _ensure_folder_exists.
            ok = await self._ensure_folder_exists(storage, folder_path)
            if not ok:
                return None

            # metadata: Яндекс.Диск поддерживает custom_properties через PATCH
            if metadata:
                try:
                    await self._request(
                        storage,
                        "PATCH",
                        f"{DISK_API_BASE}/resources",
                        params={"path": folder_path},
                        json={"custom_properties": metadata},
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to set custom_properties on %s: %s",
                        folder_path,
                        e,
                    )

            logger.info("Folder ensured in Yandex Disk: %s", folder_path)
            return folder_path

        except Exception as e:
            logger.error("Failed to create folder in Yandex Disk: %s", e)
            return None

    async def validate_connection(self, storage: "AttachmentStorage") -> bool:
        """Проверить подключение к Яндекс.Диску запросом метаданных диска."""
        if not storage.yandex_access_token:
            return False

        try:
            response = await self._request(storage, "GET", DISK_API_BASE)
            if response.status_code != 200:
                logger.error(
                    "Yandex Disk connection check failed: %s %s",
                    response.status_code,
                    response.text,
                )
                return False

            data = response.json()
            user = data.get("user", {})
            logger.info(
                "Yandex Disk connected as: %s (%s)",
                user.get("display_name") or user.get("login"),
                user.get("uid"),
            )
            return True

        except Exception as e:
            logger.error("Yandex Disk connection failed: %s", e)
            return False

    async def get_file_url(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
    ) -> str | None:
        """Получить URL файла в Яндекс.Диске."""
        if attachment.storage_file_url:
            return attachment.storage_file_url

        if attachment.storage_file_id:
            return self._build_web_url(attachment.storage_file_id)

        return None

    async def move_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        new_parent_id: str,
    ) -> dict[str, Any]:
        """Переместить файл в другую папку."""
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

        current_path = attachment.storage_file_id
        filename = current_path.rsplit("/", 1)[-1]
        new_path = self._join_path(new_parent_id, filename)

        # Гарантируем существование папки-получателя
        await self._ensure_folder_exists(storage, new_parent_id)

        try:
            response = await self._request(
                storage,
                "POST",
                f"{DISK_API_BASE}/resources/move",
                params={
                    "from": current_path,
                    "path": new_path,
                    "overwrite": "true",
                },
            )

            if response.status_code not in (200, 201, 202):
                logger.error(
                    "Failed to move Yandex file %s -> %s: %s %s",
                    current_path,
                    new_path,
                    response.status_code,
                    response.text,
                )
                response.raise_for_status()

            logger.info(
                "File moved in Yandex Disk: %s -> %s", current_path, new_path
            )

            return {
                "storage_file_id": new_path,
                "storage_parent_id": self._normalize_path(new_parent_id),
                "storage_file_url": self._build_web_url(new_path),
            }

        except Exception as e:
            logger.error("Failed to move file %s: %s", current_path, e)
            raise

    # ------------------------------------------------------------------ #
    # Утилиты
    # ------------------------------------------------------------------ #

    @classmethod
    def _build_web_url(cls, path: str) -> str:
        """
        Построить web-URL для просмотра ресурса в веб-интерфейсе Яндекс.Диска.

        URL такого вида открывает соответствующую папку.
        """
        # Папка-контейнер для файла
        if "/" in path.lstrip("/"):
            parent = path.rsplit("/", 1)[0] or "/"
        else:
            parent = "/"
        return f"{cls.file_url_base}{quote(parent)}"
