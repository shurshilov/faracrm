# Copyright 2025 FARA CRM
# Attachments Google Drive module - model mixins

from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.crm.attachments.models.attachments_storage import (
    AttachmentStorage,
)
from backend.base.system.dotorm.dotorm.decorators import onchange
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Boolean,
    Selection,
    Text,
    JSONField,
)

# Поддержка IDE - видны все атрибуты базового класса
if TYPE_CHECKING:
    _Base = AttachmentStorage
else:
    _Base = object


@extend(AttachmentStorage)
class AttachmentStorageGoogleMixin(_Base):
    """
    Миксин для AttachmentStorage с поддержкой Google Drive.

    Добавляет:
    - Тип 'google' в Selection поле type
    - Поля для OAuth2 авторизации
    - Поля для настройки Google Drive (folder_id, team drive)
    """

    # Расширяем Selection поле type
    type: str = Selection(selection_add=[("google", "Google Drive")])

    # OAuth2 авторизация
    google_json_credentials: dict | list | None = JSONField(
        string="Credentials JSON",
        help="Contents of credentials.json file from Google Cloud Console",
    )

    google_credentials: str | None = Text(
        string="Credentials (internal)",
        help="Serialized OAuth2 credentials. Do not edit manually.",
    )

    google_refresh_token: str | None = Char(
        string="Refresh Token",
        help="OAuth2 refresh token for automatic token refresh",
    )

    google_auth_state: str | None = Selection(
        options=[
            ("none", "Not configured"),
            ("pending", "Pending authorization"),
            ("authorized", "Authorized"),
            ("failed", "Authorization failed"),
        ],
        default="none",
        string="Authorization State",
    )

    google_verify_code: str | None = Char(
        string="Verification Code",
    )

    # Google Drive настройки
    google_folder_id: str | None = Char(
        string="Root Folder ID",
        help="ID of the root folder in Google Drive",
    )

    google_team_enabled: bool = Boolean(
        default=False,
        string="Use Shared Drive",
    )

    google_team_id: str | None = Char(
        string="Shared Drive ID",
    )

    @onchange("type")
    async def onchange_type_google(self) -> dict:
        """Значения по умолчанию при выборе типа google."""
        if self.type == "google":
            return {
                "google_auth_state": "none",
                "google_team_enabled": False,
            }
        return {}

    @onchange("google_team_enabled")
    async def onchange_google_team_enabled(self) -> dict:
        """Очищает team_id если team drive отключен."""
        if not self.google_team_enabled:
            return {"google_team_id": None}
        return {}
