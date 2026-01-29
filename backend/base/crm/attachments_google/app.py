# Copyright 2025 FARA CRM
# Attachments Google Drive module - application

from backend.base.system.core.app import App


class AttachmentsGoogleApp(App):
    """
    Приложение для интеграции вложений с Google Drive.

    Добавляет:
    - Стратегию хранения GoogleDriveStrategy
    - Расширение модели AttachmentStorage полями для Google Drive
    - Поддержку OAuth2 авторизации
    """

    info = {
        "name": "Attachments Google Drive",
        "summary": "Google Drive storage integration for attachments",
        "author": "FARA CRM",
        "category": "Attachments",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["attachments"],
        "sequence": 110,
    }

    def __init__(self):
        super().__init__()

        # Регистрируем стратегию Google Drive
        from backend.base.crm.attachments.strategies import register_strategy
        from backend.base.crm.attachments_google.strategies import (
            GoogleDriveStrategy,
        )

        register_strategy(GoogleDriveStrategy)

        # Импортируем миксины для применения расширений
        # flake8: noqa: F401
        from backend.base.crm.attachments_google import mixins
