# Copyright 2025 FARA CRM
# Attachments Yandex Disk module - application

from backend.base.system.core.app import App


class AttachmentsYandexApp(App):
    """
    Приложение для интеграции вложений с Яндекс.Диском.

    Добавляет:
    - Стратегию хранения YandexDiskStrategy
    - Расширение модели AttachmentStorage полями для Яндекс.Диска
    - Поддержку OAuth2 авторизации
    """

    info = {
        "name": "Attachments Yandex Disk",
        "summary": "Yandex Disk storage integration for attachments",
        "author": "FARA CRM",
        "category": "Attachments",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["attachments"],
        "sequence": 111,
    }

    def __init__(self):
        super().__init__()

        # Регистрируем стратегию Яндекс.Диск
        from backend.base.crm.attachments.strategies import register_strategy
        from backend.base.crm.attachments_yandex.strategies import (
            YandexDiskStrategy,
        )

        register_strategy(YandexDiskStrategy)
