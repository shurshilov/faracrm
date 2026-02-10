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
        Инициализация pub/sub backend для cross-process WebSocket events.

        Backend выбирается через настройку PUBSUB__BACKEND:
        - "pg"    → PostgreSQL LISTEN/NOTIFY (default, zero config)
        - "redis" → Redis Pub/Sub (requires redis server)

        Настройки (.env):
            PUBSUB__BACKEND=pg
            PUBSUB__BACKEND=redis
            PUBSUB__REDIS_URL=redis://localhost:6379/0
        """
        from .websocket.pubsub import (
            create_pubsub_backend,
            PubSubSettings,
        )
        from .websocket import chat_manager

        env: "Environment" = app.state.env

        # Загружаем настройки из env переменных
        try:
            settings = PubSubSettings()
        except Exception as e:
            logger.warning(
                f"ChatApp: failed to load PubSubSettings ({e}), "
                f"using defaults (pg backend)"
            )
            settings = PubSubSettings(backend="pg")

        # Создаём backend через фабрику (Strategy pattern)
        backend = create_pubsub_backend(settings)

        # Инициализируем в зависимости от типа
        if settings.backend == "redis":
            await backend.setup(redis_url=settings.redis_url)
            logger.info(f"ChatApp: using Redis pub/sub ({settings.redis_url})")
        else:
            # PostgreSQL — нужен asyncpg pool
            pool = env.apps.db.fara
            if not pool:
                logger.error(
                    "ChatApp: no asyncpg pool — pub/sub will not work"
                )
                return
            await backend.setup(pool=pool)
            logger.info("ChatApp: using PostgreSQL pub/sub (LISTEN/NOTIFY)")

        # Устанавливаем backend в chat_manager
        chat_manager.set_pubsub(backend)

        # Запускаем listener — каждый event будет обработан chat_manager
        await backend.start_listening(chat_manager.handle_pubsub_event)

        logger.info(
            f"ChatApp: pub/sub started (backend={settings.backend}) — "
            f"WS events are cross-process"
        )

    async def shutdown(self, app: FastAPI):
        """Остановка pub/sub backend."""
        from .websocket import chat_manager

        if chat_manager._pubsub:
            await chat_manager._pubsub.stop()
            chat_manager._pubsub = None

        logger.info("ChatApp: pub/sub stopped")

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
