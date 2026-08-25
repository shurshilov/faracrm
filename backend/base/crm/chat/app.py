# Copyright 2025 FARA CRM
# Chat module - application configuration

import asyncio
import logging
from typing import TYPE_CHECKING

from .websocket.manager import ConnectionManager, WS_REAP_INTERVAL_SECONDS
from backend.base.system.core.service import Service
from backend.base.crm.security.acl_post_init_mixin import ACL

if TYPE_CHECKING:
    from fastapi import FastAPI
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
        "ui_menu": True,
        "ui_menu_name": "communication",
        "name": "Chat",
        "summary": "Chat and messaging module with external integrations support",
        "author": "FARA CRM",
        "category": "Communication",
        "version": "1.1.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "service": True,
        "depends": [
            "security",
            "users",
            "attachments",
            "db",
            "leads",
            "tasks",
        ],
        "sequence": 90,
    }

    chat_manager: ConnectionManager

    # Фоновая уборка залипших WS-соединений (см. startup).
    _ws_reaper_task: "asyncio.Task | None" = None

    BASE_USER_ACL = {
        "chat": ACL.FULL,
        "chat_member": ACL.FULL,
        "chat_message": ACL.FULL,
        "chat_message_reaction": ACL.FULL,
        "chat_connector": ACL.FULL,
        "chat_external_account": ACL.FULL,
        "chat_external_chat": ACL.FULL,
        "chat_external_message": ACL.FULL,
        "chat_routing_rule_lead": ACL.FULL,
        "chat_folder": ACL.FULL,
    }

    async def startup(self, app: "FastAPI"):
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
        )

        env: "Environment" = app.state.env
        self.chat_manager = ConnectionManager()

        # Жнец залипших соединений. Мобильный клиент уходит молча (сон
        # вкладки, NAT оператора, WiFi↔LTE рвут TCP без close-кадра), и без
        # этой уборки он навсегда остаётся «в сети» для остальных.
        # Запускаем до pub/sub: не зависит от него и нужен даже если шина
        # не поднялась.
        self._ws_reaper_task = asyncio.create_task(self._ws_reaper_loop())

        settings = env.settings.chat

        # Создаём backend через фабрику (Strategy pattern)
        backend = create_pubsub_backend(settings)

        # Инициализируем в зависимости от типа
        if settings.pubsub_backend == "redis":
            await backend.setup(redis_url=settings.redis_url)
            logger.info(
                "ChatApp: using Redis pub/sub (%s)", settings.redis_url
            )
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
        self.chat_manager.set_pubsub(backend)

        # Один listener на канал ws_events — диспетчеризуем по типу:
        # auth-события (session_revoked / session_roles_changed) идут в
        # SessionCache через Session.handle_pubsub_event, остальное — в
        # chat_manager. Так logout/revoke и смена ролей доходят до ВСЕХ
        # воркеров (раньше session_revoked публиковался, но потребителя
        # на шине не было).
        async def _bus_dispatch(event: dict):
            etype = event.get("type")
            if etype in ("session_revoked", "session_roles_changed"):
                await env.models.session.handle_pubsub_event(event)
            else:
                await self.chat_manager.handle_pubsub_event(event)

        await backend.start_listening(_bus_dispatch)

        logger.info(
            "ChatApp: pub/sub started (backend=%s) — "
            "WS events are cross-process",
            settings.pubsub_backend,
        )

    async def _ws_reaper_loop(self):
        """Периодически выбрасывать молчащие WebSocket-соединения."""
        while True:
            await asyncio.sleep(WS_REAP_INTERVAL_SECONDS)
            try:
                await self.chat_manager.reap_stale_connections()
            except Exception:
                # Уборка не должна убивать себя из-за одного сбойного сокета.
                logger.warning(
                    "ChatApp: WS reaper iteration failed", exc_info=True
                )

    async def shutdown(self, app: "FastAPI"):
        """Остановка pub/sub backend."""

        if self._ws_reaper_task:
            self._ws_reaper_task.cancel()
            try:
                await self._ws_reaper_task
            except asyncio.CancelledError:
                pass
            self._ws_reaper_task = None

        if self.chat_manager.pubsub:
            await self.chat_manager.pubsub.stop()
            self.chat_manager.set_pubsub(None)

        logger.info("ChatApp: pub/sub stopped")

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        # await self._init_chat_rules(env)
        await self._init_membership_rules(env)
        await self._init_system_settings(env)

        # Глобальные дефолтные папки (Все/Личные/Группы). Идемпотентно.
        try:
            await env.models.chat_folder.ensure_global_defaults()
        except Exception as exc:
            logger.warning("chat_folder global defaults skipped: %s", exc)

    async def _init_membership_rules(self, env: "Environment"):
        """
        Создаёт security rules через @-операторы:

        - chat: видят только участники (через chat_member.user_id)
        - chat_message: видят те, у кого есть доступ к chat
        - chat_member: видят те, у кого есть доступ к chat
                       (не нужно смотреть участников чужих чатов)
        - chat_message_reaction: видят те, у кого есть доступ к message

        Все правила создаются с role_id=None — применяются ко всем
        ролям. is_admin / SystemSession проскакивают сами на уровне
        _is_full_access.
        """
        from backend.base.crm.security.models.rules import Rule

        # Хелпер для безопасного создания rule (role_id=None → для всех ролей).
        async def create_rule_if_missing(name, model_name, domain, perms):
            model_rec = await env.models.model.search(
                filter=[("name", "=", model_name)],
                limit=1,
            )
            if not model_rec:
                logger.warning(
                    "Model '%s' not found, skipping rule '%s'",
                    model_name,
                    name,
                )
                return
            existing = await env.models.rule.search(
                filter=[("name", "=", name)],
                limit=1,
            )
            if existing:
                return
            await env.models.rule.create(
                payload=Rule(
                    name=name,
                    active=True,
                    model_id=model_rec[0],
                    role_id=None,
                    domain=domain,
                    perm_create=perms.get("create", False),
                    perm_read=perms.get("read", False),
                    perm_update=perms.get("update", False),
                    perm_delete=perms.get("delete", False),
                ),
            )

        # Chat — chat.id IN (SELECT chat_id FROM chat_member WHERE user_id=...)
        await create_rule_if_missing(
            name="Chat: members can see and update their chats",
            model_name="chat",
            domain=[["@is_member", "id", "chat_member", "chat_id"]],
            perms={"read": True, "update": True},
        )

        # Chat (team-scoped, ЧТЕНИЕ) — правила OR-комбинируются: чат виден также,
        # если его team_id входит в команды пользователя ({{team_ids}}).
        # Только read; писать/менять — по членству (правило выше). Внутренние
        # чаты имеют team_id=NULL → в этот гейт не попадают. Кросс-командный
        # обзор («все команды») пока покрывает is_admin — отдельная роль не
        # заводится (YAGNI); ввести, если понадобится read-all-не-админ.
        await create_rule_if_missing(
            name="Chat: team members can read team chats",
            model_name="chat",
            domain=[["team_id", "in", "{{team_ids}}"]],
            perms={"read": True},
        )

        # Запрет ЛИЧНОГО (direct) чата с партнёром НЕ выражается create-правилом:
        # различающее «есть партнёр» — не поле chat, а is_internal вычисляется
        # ТРИГГЕРОМ по составу участников ПОСЛЕ вставки, тогда как create-правило
        # перепроверяет запись сразу после INSERT (мемберов ещё нет) → ложно
        # блокировало бы легитимный direct user-user. Поэтому ограничение —
        # императивное, в create_chat (chats.py), до создания, по partner_ids.

        # ChatMember — chat_member.chat_id IN (SELECT chat_id FROM chat_member WHERE user_id=...)
        # Юзер видит участников только тех чатов где он сам участник
        await create_rule_if_missing(
            name="ChatMember: visible if chat is accessible",
            model_name="chat_member",
            domain=[["@is_member", "chat_id", "chat_member", "chat_id"]],
            perms={"read": True, "update": True},
        )

        # ChatMessage ЧТЕНИЕ — через доступ к родительскому чату
        # (@has_parent_access наследует OR-домены chat: члены + team + право),
        # поэтому team-читатель видит сообщения, не будучи участником.
        await create_rule_if_missing(
            name="ChatMessage: readable if chat is accessible",
            model_name="chat_message",
            domain=[["@has_parent_access", "chat", "chat_id"]],
            perms={"read": True},
        )
        # ChatMessage ЗАПИСЬ — только участники чата (team-читатель писать не
        # может, пока не вступит).
        await create_rule_if_missing(
            name="ChatMessage: members can write",
            model_name="chat_message",
            domain=[["@is_member", "chat_id", "chat_member", "chat_id"]],
            perms={"create": True, "update": True, "delete": True},
        )

        # ChatMessageReaction — через has_parent_access на message
        await create_rule_if_missing(
            name="ChatMessageReaction: visible if message is accessible",
            model_name="chat_message_reaction",
            domain=[["@has_parent_access", "chat_message", "message_id"]],
            perms={"read": True, "create": True, "delete": True},
        )

        # ChatFolder — читать можно свои + глобальные (user_id IS NULL:
        # Все/Личные/Группы/коннекторы). Create — на уровне ACL (user_id
        # проставляется default'ом = текущий).
        await create_rule_if_missing(
            name="ChatFolder: read own and global folders",
            model_name="chat_folder",
            domain=[
                ["user_id", "=", "{{user_id}}"],
                "or",
                ["user_id", "=", None],
            ],
            perms={"read": True},
        )
        # Редактировать / удалять — ТОЛЬКО свои (у глобальных user_id IS NULL).
        await create_rule_if_missing(
            name="ChatFolder: update and delete own folders",
            model_name="chat_folder",
            domain=[["user_id", "=", "{{user_id}}"]],
            perms={"update": True, "delete": True},
        )

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

    # async def _init_chat_rules(self, env: "Environment"):
    #     """Создаёт правила безопасности для чатов и сообщений."""
    #     from backend.base.crm.security.models.rules import Rule

    #     # Правило для chat: можно удалять только свои чаты (creator_id = user_id)
    #     chat_model = await env.models.model.search(
    #         filter=[("name", "=", "chat")],
    #         limit=1,
    #     )
    #     if chat_model:
    #         rule_name = "User can only delete own chats"
    #         existing = await env.models.rule.search(
    #             filter=[("name", "=", rule_name)],
    #             limit=1,
    #         )
    #         if not existing:
    #             await env.models.rule.create(
    #                 payload=Rule(
    #                     name=rule_name,
    #                     active=True,
    #                     model_id=chat_model[0],
    #                     role_id=None,
    #                     domain=[["creator_id", "=", "{{user_id}}"]],
    #                     perm_create=False,
    #                     perm_read=False,
    #                     perm_update=False,
    #                     perm_delete=True,
    #                 ),
    #             )

    #     # Правило для chat_message: можно удалять только свои сообщения (author_id = user_id)
    #     message_model = await env.models.model.search(
    #         filter=[("name", "=", "chat_message")],
    #         limit=1,
    #     )
    #     if message_model:
    #         rule_name = "User can only delete and edit own messages"
    #         existing = await env.models.rule.search(
    #             filter=[("name", "=", rule_name)],
    #             limit=1,
    #         )
    #         if not existing:
    #             await env.models.rule.create(
    #                 payload=Rule(
    #                     name=rule_name,
    #                     active=True,
    #                     model_id=message_model[0],
    #                     role_id=None,
    #                     domain=[["author_user_id", "=", "{{user_id}}"]],
    #                     perm_create=False,
    #                     perm_read=False,
    #                     perm_update=True,  # Редактировать тоже только свои
    #                     perm_delete=True,
    #                 ),
    #             )
