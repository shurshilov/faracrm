# Copyright 2025 FARA CRM
# Chat module - application configuration

from fastapi import FastAPI
from typing import TYPE_CHECKING

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment


class ChatApp(App):
    """
    Приложение чата и обмена сообщениями.

    Функциональность:
    - Внутренний чат между пользователями
    - Real-time обмен через WebSocket
    - Интеграция с внешними мессенджерами (Telegram, WhatsApp, Avito и др.)
    - Поддержка каналов и групповых чатов
    - Вложения (файлы, изображения)
    """

    info = {
        "name": "Chat",
        "summary": "Chat and messaging module with external integrations support",
        "author": "FARA CRM",
        "category": "Communication",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security", "users", "attachments"],
    }

    BASE_USER_ACL = {
        "chat": ACL.FULL,
        "chat_member": ACL.FULL,
        "chat_message": ACL.FULL,
        "chat_message_reaction": ACL.FULL,
        "chat_connector": ACL.FULL,
        "chat_external_account": ACL.FULL,
        "chat_external_chat": ACL.FULL,
        "chat_external_message": ACL.FULL,
    }

    async def post_init(self, app: FastAPI):
        await super().post_init(app)
        env: "Environment" = app.state.env

        await self._init_chat_rules(env)
        await self._init_system_settings(env)

    async def _init_system_settings(self, env: "Environment"):
        """Создаёт настройки по умолчанию для модуля chat."""
        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": "chat.max_file_size",
                    "value": {"value": 10 * 1024 * 1024},
                    "description": "Максимальный размер файла в чате в байтах (по умолчанию 10 МБ)",
                    "module": "chat",
                    "is_system": False,
                    "cache_ttl": -1,
                },
            ]
        )

    async def _init_chat_rules(self, env: "Environment"):
        """Создаёт правила безопасности для чатов и сообщений."""
        from backend.base.crm.security.models.rules import Rule

        # Правило для chat: можно удалять только свои чаты (creator_id = user_id)
        chat_model = await env.models.model.search(
            filter=[("name", "=", "chat")],
            limit=1,
        )
        if chat_model:
            rule_name = "User can only delete own chats"
            existing = await env.models.rule.search(
                filter=[("name", "=", rule_name)],
                limit=1,
            )
            if not existing:
                await env.models.rule.create(
                    payload=Rule(
                        name=rule_name,
                        active=True,
                        model_id=chat_model[0],
                        role_id=None,
                        domain=[["creator_id", "=", "{{user_id}}"]],
                        perm_create=False,
                        perm_read=False,
                        perm_update=False,
                        perm_delete=True,
                    ),
                )

        # Правило для chat_message: можно удалять только свои сообщения (author_id = user_id)
        message_model = await env.models.model.search(
            filter=[("name", "=", "chat_message")],
            limit=1,
        )
        if message_model:
            rule_name = "User can only delete own messages"
            existing = await env.models.rule.search(
                filter=[("name", "=", rule_name)],
                limit=1,
            )
            if not existing:
                await env.models.rule.create(
                    payload=Rule(
                        name=rule_name,
                        active=True,
                        model_id=message_model[0],
                        role_id=None,
                        domain=[["author_user_id", "=", "{{user_id}}"]],
                        perm_create=False,
                        perm_read=False,
                        perm_update=True,  # Редактировать тоже только свои
                        perm_delete=True,
                    ),
                )
