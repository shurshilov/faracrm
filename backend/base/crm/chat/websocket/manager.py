# Copyright 2025 FARA CRM
# Chat module - WebSocket manager for real-time messaging

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Set

from fastapi import WebSocket
from starlette.websockets import WebSocketState

if TYPE_CHECKING:
    from .pubsub.base import PubSubBackend

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Менеджер WebSocket соединений для чата.

    Поддерживает множественные подключения одного пользователя
    (несколько вкладок, устройств).

    Управляет:
    - Подключениями пользователей (1 user → N websockets)
    - Подписками на чаты
    - Рассылкой сообщений участникам чата
    - Статусами онлайн/оффлайн
    """

    def __init__(self):
        # user_id -> set of WebSocket connections
        self._connections: dict[int, Set[WebSocket]] = {}

        # chat_id -> set of user_ids subscribed to this chat
        self._chat_subscriptions: dict[int, Set[int]] = {}

        # user_id -> set of chat_ids user is subscribed to
        self._user_subscriptions: dict[int, Set[int]] = {}

        # user_id -> last activity timestamp
        self._user_activity: dict[int, datetime] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        # PubSub backend — устанавливается при startup через set_pubsub()
        self._pubsub: "PubSubBackend | None" = None

    def set_pubsub(self, backend: "PubSubBackend") -> None:
        """Установить pub/sub backend. Вызывается из ChatApp.startup()."""
        self._pubsub = backend

    @property
    def pubsub(self) -> "PubSubBackend | None":
        """Текущий pub/sub backend (read-only)."""
        return self._pubsub

    async def connect(self, websocket: WebSocket, user_id: int) -> bool:
        """
        Подключить пользователя.
        Поддерживает множественные подключения (вкладки, устройства).

        Args:
            websocket: WebSocket соединение (уже accepted)
            user_id: ID пользователя

        Returns:
            True если успешно подключен
        """
        try:
            now = datetime.now(timezone.utc)
            async with self._lock:
                if user_id not in self._connections:
                    self._connections[user_id] = set()

                if user_id not in self._user_subscriptions:
                    self._user_subscriptions[user_id] = set()

                self._connections[user_id].add(websocket)
                self._user_activity[user_id] = now

                total_connections = len(self._connections[user_id])

            logger.info(
                "User %s connected to WebSocket (total connections: %s)",
                user_id,
                total_connections,
            )

            # Отправляем подтверждение подключения ТОЛЬКО этому websocket
            await self._send_to_websocket(
                websocket,
                {
                    "type": "connected",
                    "user_id": user_id,
                    "timestamp": now.isoformat(),
                },
            )

            return True

        except Exception as e:
            logger.error("Error connecting user %s: %s", user_id, e)
            return False

    async def disconnect(self, websocket: WebSocket, user_id: int):
        """
        Отключить конкретное WebSocket соединение пользователя.

        Под одним локом:
        - снимаем сокет и чистим структуры, если это последнее соединение;
        - собираем согласованный снимок подписчиков общих чатов,
          которым нужно разослать presence=offline.

        Сетевой broadcast выполняется строго вне лока.

        Args:
            websocket: WebSocket соединение для отключения
            user_id: ID пользователя
        """
        is_last = False
        remaining_count = 0
        notified: set[int] = set()

        async with self._lock:
            conns = self._connections.get(user_id)
            if conns is None:
                return
            conns.discard(websocket)

            if conns:
                remaining_count = len(conns)
            else:
                is_last = True
                del self._connections[user_id]
                self._user_activity.pop(user_id, None)

                user_chat_ids = self._user_subscriptions.pop(user_id, set())
                for chat_id in user_chat_ids:
                    subs = self._chat_subscriptions.get(chat_id)
                    if subs is None:
                        continue
                    subs.discard(user_id)
                    # Под этим же локом склеиваем получателей —
                    # снимок согласован с моментом disconnect.
                    notified.update(subs)

        logger.info(
            "User %s disconnected from WebSocket (remaining connections: %s)",
            user_id,
            remaining_count,
        )

        # Уведомляем о выходе — только если это было последнее подключение
        if is_last and notified:
            presence_msg = {
                "type": "presence",
                "user_id": user_id,
                "status": "offline",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await asyncio.gather(
                *[self._send_to_user(uid, presence_msg) for uid in notified],
                return_exceptions=True,
            )

    async def subscribe_to_chats(self, user_id: int, chat_ids: list[int]):
        """
        Подписать пользователя на несколько чатов одной операцией.

        Делает две симметричные вещи при онлайн-юзере:
        1. Шлёт presence=online всем ранее известным подписчикам общих чатов
           (чтобы они узнали, что юзер появился).
        2. Шлёт самому юзеру presence_snapshot со списком тех, кто уже онлайн
           в этих чатах (чтобы он сразу знал, кто из собеседников в сети).

        Это основной путь presence при первом подключении: клиент после
        WS-accept шлёт subscribe_all со своим списком чатов, и только здесь
        сервер узнаёт, кому сообщать и что сообщить подключившемуся.

        Args:
            user_id: ID пользователя
            chat_ids: Список ID чатов
        """
        if not chat_ids:
            return

        # Подписчики ДО нас одновременно:
        #  - получатели presence=online про нас (push),
        #  - онлайн-пиры, о которых сообщаем нам (snapshot в ответ).
        notified: set[int] = set()
        user_online = False

        async with self._lock:
            if user_id not in self._user_subscriptions:
                self._user_subscriptions[user_id] = set()

            user_online = bool(self._connections.get(user_id))

            for chat_id in chat_ids:
                if chat_id not in self._chat_subscriptions:
                    self._chat_subscriptions[chat_id] = set()

                # Собираем существующих подписчиков ТОЛЬКО для чатов,
                # где юзер реально впервые — иначе присутствие уже известно.
                if user_id not in self._chat_subscriptions[chat_id]:
                    notified.update(self._chat_subscriptions[chat_id])

                self._chat_subscriptions[chat_id].add(user_id)
                self._user_subscriptions[user_id].add(chat_id)

            notified.discard(user_id)

        logger.info("User %s subscribed to %s chats", user_id, len(chat_ids))

        if not (user_online and notified):
            return

        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Юзеру — snapshot онлайн-пиров (одним кадром, меньше шума фронту).
        await self._send_to_user(
            user_id,
            {
                "type": "presence_snapshot",
                "users": sorted(notified),
                "timestamp": timestamp,
            },
        )

        # 2. Остальным — presence=online про юзера, параллельно.
        presence_msg = {
            "type": "presence",
            "user_id": user_id,
            "status": "online",
            "timestamp": timestamp,
        }
        await asyncio.gather(
            *[self._send_to_user(uid, presence_msg) for uid in notified],
            return_exceptions=True,
        )

    async def unsubscribe_from_chat(self, user_id: int, chat_id: int):
        """
        Отписать пользователя от чата.

        Args:
            user_id: ID пользователя
            chat_id: ID чата
        """
        async with self._lock:
            if chat_id in self._chat_subscriptions:
                self._chat_subscriptions[chat_id].discard(user_id)

            if user_id in self._user_subscriptions:
                self._user_subscriptions[user_id].discard(chat_id)

        logger.debug("User %s unsubscribed from chat %s", user_id, chat_id)

    async def send_to_chat(
        self, chat_id: int, message: dict, exclude_user: int | None = None
    ):
        """
        Отправить сообщение всем участникам чата (CROSS-PROCESS).
        Проходит через pg_notify → все workers.
        """
        if self._pubsub:
            await self._pubsub.publish(
                "send_to_chat",
                {
                    "chat_id": chat_id,
                    "message": message,
                    "exclude_user": exclude_user,
                },
            )

    async def send_to_user(self, user_id: int, message: dict):
        """
        Отправить сообщение пользователю (CROSS-PROCESS).
        Проходит через pg_notify → все workers.
        """
        if self._pubsub:
            await self._pubsub.publish(
                "send_to_user",
                {
                    "user_id": user_id,
                    "message": message,
                },
            )

    async def notify_new_chat(self, user_id: int, chat_id: int):
        """
        Уведомить пользователя о новом чате (CROSS-PROCESS).
        Проходит через pg_notify → все workers.
        """
        if self._pubsub:
            await self._pubsub.publish(
                "notify_new_chat",
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                },
            )

    # ──────────────────────────────────────────────
    # PG_NOTIFY EVENT HANDLER
    # Вызывается при получении event от PostgreSQL LISTEN.
    # Выполняет ЛОКАЛЬНУЮ доставку в WebSocket connections этого worker-а.
    # ──────────────────────────────────────────────

    async def handle_pubsub_event(self, event: dict):
        """Обработчик event-ов от pubsub."""
        event_type = event.get("type")

        if event_type == "send_to_chat":
            chat_id = event["chat_id"]
            message = event["message"]
            exclude_user = event.get("exclude_user")
            async with self._lock:
                subscribers = self._chat_subscriptions.get(
                    chat_id, set()
                ).copy()
            for user_id in subscribers:
                if exclude_user and user_id == exclude_user:
                    continue
                await self._send_to_user(user_id, message)

        elif event_type == "send_to_user":
            await self._send_to_user(event["user_id"], event["message"])

        elif event_type == "notify_new_chat":
            user_id = event["user_id"]
            chat_id = event["chat_id"]
            await self.subscribe_to_chats(user_id, [chat_id])
            await self._send_to_user(
                user_id, {"type": "chat_created", "chat_id": chat_id}
            )

    async def _send_to_websocket(self, ws: WebSocket, message: dict) -> bool:
        """Отправить в один сокет. Если сдох — удалить из всех списков."""
        if ws.client_state == WebSocketState.CONNECTED:
            try:
                await ws.send_json(message)
                return True
            except Exception as e:
                logger.error("WS send failed: %s", e)

        await self._remove_websocket(ws)
        return False

    async def _remove_websocket(self, ws: WebSocket) -> None:
        """Удалить сокет из всех user-бакетов."""
        async with self._lock:
            empty = []
            for uid, bucket in self._connections.items():
                bucket.discard(ws)
                if not bucket:
                    empty.append(uid)
            for uid in empty:
                self._connections.pop(uid, None)

    async def _send_to_user(self, user_id: int, message: dict):
        """
        Отправить сообщение во все соединения пользователя.

        Args:
            user_id: ID пользователя
            message: Сообщение
        """
        async with self._lock:
            websockets = list(self._connections.get(user_id, ()))
        if websockets:
            await asyncio.gather(
                *(self._send_to_websocket(ws, message) for ws in websockets)
            )

    # async def _broadcast_presence(self, user_id: int, status: str):
    #     """
    #     Разослать presence-статус всем онлайн-участникам общих чатов юзера.

    #     Под одним локом собираем согласованный снимок получателей
    #     (онлайн-подписчики чатов юзера, кроме него самого),
    #     затем выполняем рассылку через asyncio.gather вне лока.

    #     В текущем flow напрямую не вызывается — subscribe_to_chat(s) и
    #     disconnect формируют свой более точный снимок. Метод оставлен
    #     для будущих сценариев массового re-broadcast: например,
    #     presence=offline по таймауту неактивности.

    #     Args:
    #         user_id: ID пользователя
    #         status: Статус (online/offline)
    #     """
    #     async with self._lock:
    #         user_chats = self._user_subscriptions.get(user_id, set())
    #         notified: set[int] = set()
    #         for chat_id in user_chats:
    #             subs = self._chat_subscriptions.get(chat_id)
    #             if subs:
    #                 notified.update(subs)
    #         notified.discard(user_id)

    #     if not notified:
    #         return

    #     presence_msg = {
    #         "type": "presence",
    #         "user_id": user_id,
    #         "status": status,
    #         "timestamp": datetime.now(timezone.utc).isoformat(),
    #     }

    #     await asyncio.gather(
    #         *[self._send_to_user(uid, presence_msg) for uid in notified],
    #         return_exceptions=True,
    #     )

    # def is_online(self, user_id: int) -> bool:
    #     """Проверить онлайн ли пользователь."""
    #     return bool(self._connections.get(user_id))

    # def get_online_users(self) -> list[int]:
    #     """Получить список онлайн пользователей."""
    #     return [uid for uid, conns in self._connections.items() if conns]

    # def get_chat_online_users(self, chat_id: int) -> list[int]:
    #     """Получить онлайн пользователей в конкретном чате."""
    #     subscribers = self._chat_subscriptions.get(chat_id, set())
    #     return [uid for uid in subscribers if self.is_online(uid)]

    async def handle_message(
        self, websocket: WebSocket, user_id: int, data: dict
    ):
        """
        Обработать входящее сообщение от клиента.

        Args:
            websocket: WebSocket соединение, от которого пришло сообщение
            user_id: ID пользователя
            data: Данные сообщения
        """
        message_type = data.get("type")

        if message_type == "ping":
            # Heartbeat — отвечаем только в этот websocket
            async with self._lock:
                self._user_activity[user_id] = datetime.now(timezone.utc)
            await self._send_to_websocket(websocket, {"type": "pong"})

        elif message_type == "subscribe":
            # Подписка на чат
            chat_id = data.get("chat_id")
            if chat_id:
                await self.subscribe_to_chats(user_id, [chat_id])
                await self._send_to_websocket(
                    websocket, {"type": "subscribed", "chat_id": chat_id}
                )

        elif message_type == "subscribe_all":
            # Подписка на несколько чатов одним запросом
            chat_ids = data.get("chat_ids", [])
            if chat_ids:
                await self.subscribe_to_chats(user_id, chat_ids)
                await self._send_to_websocket(
                    websocket,
                    {
                        "type": "subscribed_all",
                        "chat_ids": chat_ids,
                        "count": len(chat_ids),
                    },
                )

        elif message_type == "unsubscribe":
            # Отписка от чата
            chat_id = data.get("chat_id")
            if chat_id:
                await self.unsubscribe_from_chat(user_id, chat_id)
                await self._send_to_websocket(
                    websocket, {"type": "unsubscribed", "chat_id": chat_id}
                )

        elif message_type == "typing":
            # Индикатор набора текста
            chat_id = data.get("chat_id")
            if chat_id:
                await self.send_to_chat(
                    chat_id,
                    {
                        "type": "typing",
                        "chat_id": chat_id,
                        "user_id": user_id,
                    },
                    exclude_user=user_id,
                )

        elif message_type == "read":
            # Отметка о прочтении
            chat_id = data.get("chat_id")
            message_id = data.get("message_id")
            if chat_id:
                await self.send_to_chat(
                    chat_id,
                    {
                        "type": "messages_read",
                        "chat_id": chat_id,
                        "user_id": user_id,
                        "message_id": message_id,
                    },
                    exclude_user=user_id,
                )
