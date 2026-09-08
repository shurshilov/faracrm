# Copyright 2025 FARA CRM
# Attachments Git module - storage strategy (GitHub, read-only)

import ast
import io
import logging
import re
import zipfile
from typing import TYPE_CHECKING, Any

import httpx

from backend.base.crm.attachments.strategies.strategy import (
    StorageStrategyBase,
)

if TYPE_CHECKING:
    from backend.project_setup import AttachmentStorage
    from backend.base.crm.attachments.models.attachments import Attachment

logger = logging.getLogger(__name__)

# Жёсткий шаблон — это и защита: сервер ходит с токеном только на
# api.github.com за репозиторием, который указан в хранилище.
GITHUB_REPO_RE = re.compile(
    r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$"
)
HTTP_TIMEOUT = 60.0
# Папка фронтенда модуля: frontend/src/fara_<модуль>.
FRONTEND_PREFIX = "fara_"


def parse_file_id(file_id: str | None) -> tuple[str, list[str]]:
    """storage_file_id «ref:модуль1,модуль2» → (ref, модули); пустой ref — из хранилища."""
    ref, _, names = (file_id or "").partition(":")
    return ref.strip(), [n.strip() for n in names.split(",") if n.strip()]


def module_folders(names: list[str], files: list[str]) -> set[str]:
    """
    Папки модулей среди файлов репозитория (пути от корня).

    Где лежит модуль, знать не нужно — ищем по имени в любой подпапке:
    бэкенд — папка «модуль» с app.py внутри, фронт — папка «fara_модуль».
    """
    fronts = {FRONTEND_PREFIX + name for name in names}
    folders = set()
    for path in files:
        parts = path.split("/")
        if parts[-1] == "app.py" and len(parts) > 1 and parts[-2] in names:
            folders.add("/".join(parts[:-1]))
        for depth, part in enumerate(parts[:-1], 1):
            if part in fronts:
                folders.add("/".join(parts[:depth]))
    return folders


def repack(archive: bytes, names: list[str]) -> bytes:
    """
    Из архива репозитория оставить только папки модулей.

    GitHub кладёт всё в верхнюю папку «owner-repo-sha» — её срезаем, пути в
    результате идут от корня репозитория: архив распаковывается прямо в
    проект.
    """
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(archive)) as src,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        files = {
            info.filename.split("/", 1)[1]: info
            for info in src.infolist()
            if not info.is_dir() and "/" in info.filename
        }
        folders = module_folders(names, list(files))
        for path, info in files.items():
            if any(path.startswith(folder + "/") for folder in folders):
                dst.writestr(path, src.read(info))
    return out.getvalue()


def parse_app_info(source: bytes) -> dict | None:
    """
    Словарь info из app.py модуля (как у App).

    None — info нет, это не модуль; {} — info есть, но не из литералов
    (имя и версию возьмут по умолчанию).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "info"
            for target in node.targets
        ):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                return {}
            return value if isinstance(value, dict) else {}
    return None


def list_modules(archive: bytes) -> dict[str, dict]:
    """
    Модули репозитория: {код: info}. Модуль — папка с app.py, в котором
    объявлен словарь info; код = имя папки. Ищется в любой подпапке.
    """
    modules: dict[str, dict] = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as src:
        for info in src.infolist():
            parts = info.filename.split("/")
            # «owner-repo-sha / … / модуль / app.py»
            if parts[-1] != "app.py" or len(parts) < 3:
                continue
            meta = parse_app_info(src.read(info))
            if meta is not None:
                modules[parts[-2]] = meta
    return modules


async def fetch_archive(
    storage: "AttachmentStorage", ref: str
) -> bytes | None:
    """Архив репозитория хранилища на ветке/теге; None — GitHub не отдал."""
    match = GITHUB_REPO_RE.match(storage.git_repo_url or "")
    if not match:
        raise ValueError(
            f"Git storage {storage.id}: repository URL must be "
            "https://github.com/owner/repo"
        )
    owner, repo = match.groups()

    headers = {"Accept": "application/vnd.github+json"}
    if storage.git_token:
        headers["Authorization"] = f"Bearer {storage.git_token}"

    # zipball отвечает редиректом на codeload; httpx на чужой хост
    # Authorization не переносит — токен наружу не утекает.
    url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{ref}"
    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT, follow_redirects=True
        ) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as e:
        # Сеть/TLS (например, антивирус или прокси подменяет сертификат):
        # причина в логе, наружу — «GitHub не отдал архив».
        logger.error("Git storage %s: %s for %s", storage.id, e, url)
        return None
    if response.status_code != 200:
        logger.error(
            "Git storage %s: GitHub %s for %s",
            storage.id,
            response.status_code,
            url,
        )
        return None
    return response.content


class GitStorageStrategy(StorageStrategyBase):
    """
    Хранилище-репозиторий GitHub, только чтение.

    Вложение описывает модули репозитория на ветке/теге
    (storage_file_id = «ref:модуль1,модуль2»); при чтении сервер качает
    архив репозитория через API и оставляет в нём только папки этих модулей,
    найденные по имени (см. module_folders). Загрузка и изменение файлов не
    поддерживаются — это витрина кода, а не диск.
    """

    strategy_type = "git"

    async def read_file(
        self, storage: "AttachmentStorage", attachment: "Attachment"
    ) -> bytes | None:
        ref, names = parse_file_id(attachment.storage_file_id)
        ref = ref or storage.git_ref or "HEAD"
        archive = await fetch_archive(storage, ref)
        if archive is None:
            return None

        self._log_operation("read_file", attachment, ref=ref, modules=names)
        return repack(archive, names)

    async def create_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: bytes,
        filename: str,
        mimetype: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("Git storage is read-only")

    async def update_file(
        self,
        storage: "AttachmentStorage",
        attachment: "Attachment",
        content: bytes | None = None,
        filename: str | None = None,
        mimetype: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("Git storage is read-only")

    async def delete_file(
        self, storage: "AttachmentStorage", attachment: "Attachment"
    ) -> bool:
        # В репозитории ничего не создавалось — удалять нечего.
        return True
