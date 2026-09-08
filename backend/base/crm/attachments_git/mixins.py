# Copyright 2025 FARA CRM
# Attachments Git module - model mixins

from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.crm.attachments.models.attachments_storage import (
    AttachmentStorage,
)
from backend.base.system.dotorm.dotorm.fields import Char, Selection

# Поддержка IDE - видны все атрибуты базового класса
if TYPE_CHECKING:
    _Base = AttachmentStorage
else:
    _Base = object


@extend(AttachmentStorage)
class AttachmentStorageGitMixin(_Base):
    """
    Миксин для AttachmentStorage с поддержкой GitHub-репозитория.

    Хранилище = один репозиторий. Вложение в нём — набор папок репозитория
    на ветке/теге, архив которых сервер собирает при чтении (см.
    GitStorageStrategy). Записывать в такое хранилище нельзя, поэтому оно
    не бывает active и не участвует в маршрутах загрузки.
    """

    # Расширяем Selection поле type
    type: str = Selection(selection_add=[("git", "GitHub")])

    git_repo_url: str | None = Char(
        max_length=512,
        string="Repository URL",
        help="https://github.com/owner/repo",
    )
    git_ref: str | None = Char(
        max_length=128,
        default="master",
        string="Default ref",
        help="Ветка, тег или коммит по умолчанию",
    )
    git_token: str | None = Char(
        max_length=255,
        string="Access token",
        help=(
            "Токен GitHub только на чтение содержимого: приватные "
            "репозитории и лимиты API. Наружу не отдаётся."
        ),
    )
