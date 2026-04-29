# Copyright 2025 FARA CRM
# Attachments Yandex Disk module - model mixins

from typing import TYPE_CHECKING

from backend.base.system.core.extensions import extend
from backend.base.crm.attachments.models.attachments_storage import (
    AttachmentStorage,
)
from backend.base.system.dotorm.dotorm.decorators import onchange
from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Selection,
    Text,
)

# Поддержка IDE - видны все атрибуты базового класса
if TYPE_CHECKING:
    _Base = AttachmentStorage
else:
    _Base = object


@extend(AttachmentStorage)
class AttachmentStorageYandexMixin(_Base):
    """
    Миксин для AttachmentStorage с поддержкой Яндекс.Диска.

    Добавляет:
    - Тип 'yandex' в Selection поле type
    - Поля для OAuth2 авторизации (client_id / client_secret / токены)
    - Поле для корневой папки (путь)
    """

    # Расширяем Selection поле type
    type: str = Selection(selection_add=[("yandex", "Yandex Disk")])

    # OAuth2 приложение (выдаётся в кабинете oauth.yandex.ru)
    yandex_client_id: str | None = Char(
        string="Client ID",
        help="OAuth Client ID, полученный на https://oauth.yandex.ru",
    )

    yandex_client_secret: str | None = Char(
        string="Client Secret",
        help="OAuth Client Secret, полученный на https://oauth.yandex.ru",
    )

    # Токены OAuth2 (заполняются после авторизации)
    yandex_access_token: str | None = Text(
        string="Access Token (internal)",
        help="OAuth2 access token. Не редактируйте вручную.",
    )

    yandex_refresh_token: str | None = Char(
        string="Refresh Token",
        help="OAuth2 refresh token для автоматического обновления access token",
    )

    yandex_token_expires_at: str | None = Char(
        string="Token Expires At",
        help="ISO timestamp в UTC, когда истекает access token",
    )

    yandex_auth_state: str | None = Selection(
        options=[
            ("none", "Not configured"),
            ("pending", "Pending authorization"),
            ("authorized", "Authorized"),
            ("failed", "Authorization failed"),
        ],
        default="none",
        string="Authorization State",
    )

    yandex_verify_code: str | None = Char(
        string="Verification Code",
    )

    # Настройки папки на Яндекс.Диске.
    # В отличие от Google Drive здесь не ID, а путь (например, "/CRM" или "app:/").
    # Пустое значение => корень "/".
    yandex_folder_path: str | None = Char(
        string="Root Folder Path",
        help="Путь к папке на Яндекс.Диске для хранения файлов (например, /CRM)",
    )

    @onchange("type")
    async def onchange_type_yandex(self) -> dict:
        """Значения по умолчанию при выборе типа yandex."""
        if self.type == "yandex":
            return {
                "yandex_auth_state": "none",
            }
        return {}
