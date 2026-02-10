# Copyright 2025 FARA CRM
# Chat module - application configuration

import logging
from fastapi import FastAPI
from typing import TYPE_CHECKING

from backend.base.system.core.service import Service
from backend.base.crm.security.acl_post_init_mixin import ACL

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)


class ChatApp(Service):
    """
    Приложение чата и обмена сообщениями.

    Функциональность:
    - Внутренний чат между пользователями
    - Real-time обмен через WebSocket + PostgreSQL pub/sub
    - Интеграция с внешними мессенджерами (Telegram, WhatsApp, Avito и др.)
    - Поддержка каналов и групповых чатов
    - Вложения (файлы, изображения)
    """

    info = {
        "name": "Chat",
        "summary": "Chat and messaging module with external integrations support",
        "author": "FARA CRM",
        "category": "Communication",
        "version": "1.1.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "service": True,
        "depends": ["security", "users", "attachments", "db"],
        "sequence": 90,
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

    async def startup(self, app: FastAPI):
        """
        Инициализация pg_pubsub для cross-process WebSocket events.
        Запускает LISTEN на PostgreSQL канале 'ws_events'.
        """
        from .websocket.pg_pubsub import pg_pubsub
        from .websocket import chat_manager

        env: "Environment" = app.state.env
        pool = env.apps.db.fara

        if not pool:
            logger.error(
                "ChatApp: no asyncpg pool found — "
                "pg_pubsub will not work, WS events won't be cross-process"
            )
            return

        # Инициализируем pg_pubsub
        await pg_pubsub.setup(pool)

        # Запускаем LISTEN — каждый event будет обработан chat_manager
        await pg_pubsub.start_listening(chat_manager.handle_pg_event)

        logger.info("ChatApp: pg_pubsub started — WS events are cross-process")

    async def shutdown(self, app: FastAPI):
        """Остановка pg_pubsub."""
        from .websocket.pg_pubsub import pg_pubsub

        await pg_pubsub.stop()
        logger.info("ChatApp: pg_pubsub stopped")

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
