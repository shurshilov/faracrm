# Copyright 2025 FARA CRM
# Attachments Git module - application

from backend.base.system.core.app import App


class AttachmentsGitApp(App):
    """
    Вложения из GitHub-репозитория: хранилище типа «git» (только чтение).

    Добавляет стратегию GitStorageStrategy и поля репозитория/токена в
    AttachmentStorage. Хранилище админ создаёт сам в «Файлы → Хранилища»
    (неактивным: активное хранилище принимает новые загрузки, а в git
    писать нельзя). Использует маркетплейс: архив модуля — вложение в таком
    хранилище, сервер собирает его из репозитория при скачивании.
    """

    info = {
        "name": "Attachments Git",
        "summary": "GitHub repository as a read-only attachment storage",
        "author": "FARA CRM",
        "category": "Attachments",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["attachments"],
        "sequence": 112,
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.attachments.strategies import register_strategy
        from backend.base.crm.attachments_git.strategies import (
            GitStorageStrategy,
        )

        register_strategy(GitStorageStrategy)
