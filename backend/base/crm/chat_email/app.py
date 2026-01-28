# Copyright 2025 FARA CRM
# Chat Email module - application

from fastapi import FastAPI

from backend.base.system.core.app import App


class ChatEmailApp(App):
    """Приложение для интеграции с Email через SMTP/IMAP."""

    info = {
        "name": "Chat Email",
        "summary": "Email integration for chat module (SMTP/IMAP)",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat", "cron"],
        "sequence": 125,
        "post_init": True,
    }

    def __init__(self):
        super().__init__()

        # Регистрируем стратегию
        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_email.strategies import EmailStrategy

        register_strategy(EmailStrategy)

    async def post_init(self, app: FastAPI):
        """
        Инициализация после загрузки всех модулей.
        Создаёт cron job для периодического получения email.
        """
        await super().post_init(app)

        from backend.base.system.core.enviroment import env

        # Создаём cron job для фетчинга email
        # По умолчанию неактивен - нужно включить вручную
        await env.models.cron_job.create_or_update(
            env=env,
            name="Email: Fetch new messages",
            code="""
from backend.base.crm.chat_email.strategies import EmailStrategy
result = await EmailStrategy.cron_fetch_emails(env)
""",
            interval_number=5,
            interval_type="minutes",
            active=False,  # По умолчанию выключен
            priority=20,
        )
