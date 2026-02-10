# Copyright 2025 FARA CRM
# Chat module - WebSocket manager for real-time messaging

import asyncio
import logging
from typing import Dict, Set
from datetime import datetime, timezone

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from .pg_pubsub import pg_pubsub

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
        self._connections: Dict[int, Set[WebSocket]] = {}

        # chat_id -> set of user_ids subscribed to this chat
        self._chat_subscriptions: Dict[int, Set[int]] = {}

        # user_id -> set of chat_ids user is subscribed to
        self._user_subscriptions: Dict[int, Set[int]] = {}

        # user_id -> last activity timestamp
        self._user_activity: Dict[int, datetime] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

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
            async with self._lock:
                if user_id not in self._connections:
                    self._connections[user_id] = set()
                self._connections[user_id].add(websocket)
                self._user_activity[user_id] = datetime.now(timezone.utc)

                if user_id not in self._user_subscriptions:
                    self._user_subscriptions[user_id] = set()

            was_offline = len(self._connections.get(user_id, set())) == 1

            logger.info(
                f"User {user_id} connected to WebSocket "
                f"(total connections: {len(self._connections.get(user_id, set()))})"
            )

            # Отправляем подтверждение подключения ТОЛЬКО этому websocket
            await self._send_to_websocket(
                websocket,
                {
                    "type": "connected",
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Уведомляем других о появлении — только если это первое подключение
            if was_offline:
                await self._broadcast_presence(user_id, "online")

            return True

        except Exception as e:
            logger.error(f"Error connecting user {user_id}: {e}")
            return False

    async def disconnect(self, websocket: WebSocket, user_id: int):
        """
        Отключить конкретное WebSocket соединение пользователя.

        Args:
            websocket: WebSocket соединение для отключения
            user_id: ID пользователя
        """
        is_last = False

        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id].discard(websocket)

                if not self._connections[user_id]:
                    # Последнее подключение — удаляем всё
                    del self._connections[user_id]
                    is_last = True

                    # Удаляем из всех подписок на чаты
                    if user_id in self._user_subscriptions:
                        for chat_id in self._user_subscriptions[user_id]:
                            if chat_id in self._chat_subscriptions:
                                self._chat_subscriptions[chat_id].discard(
                                    user_id
                                )
                        del self._user_subscriptions[user_id]

                    # Удаляем активность
                    if user_id in self._user_activity:
                        del self._user_activity[user_id]

        remaining = len(self._connections.get(user_id, set()))
        logger.info(
            f"User {user_id} disconnected from WebSocket "
            f"(remaining connections: {remaining})"
        )

        # Уведомляем о выходе — только если это было последнее подключение
        if is_last:
            await self._broadcast_presence(user_id, "offline")

    async def subscribe_to_chat(self, user_id: int, chat_id: int):
        """
        Подписать пользователя на чат.

        Args:
            user_id: ID пользователя
            chat_id: ID чата
        """
        async with self._lock:
            if chat_id not in self._chat_subscriptions:
                self._chat_subscriptions[chat_id] = set()

            # Запоминаем кто уже был подписан до нас
            existing_subscribers = self._chat_subscriptions[chat_id].copy()
            is_new = user_id not in self._chat_subscriptions[chat_id]

            self._chat_subscriptions[chat_id].add(user_id)

            if user_id not in self._user_subscriptions:
                self._user_subscriptions[user_id] = set()

            self._user_subscriptions[user_id].add(chat_id)

        logger.debug(f"User {user_id} subscribed to chat {chat_id}")

        # Если пользователь новый в этом чате — уведомляем остальных о его присутствии
        if is_new and self.is_online(user_id):
            presence_msg = {
                "type": "presence",
                "user_id": user_id,
                "status": "online",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for subscriber_id in existing_subscribers:
                if subscriber_id != user_id:
                    await self._send_to_user(subscriber_id, presence_msg)

    async def subscribe_to_chats(self, user_id: int, chat_ids: list[int]):
        """
        Подписать пользователя на несколько чатов одной операцией.

        Args:
            user_id: ID пользователя
            chat_ids: Список ID чатов
        """
        async with self._lock:
            if user_id not in self._user_subscriptions:
                self._user_subscriptions[user_id] = set()

            for chat_id in chat_ids:
                if chat_id not in self._chat_subscriptions:
                    self._chat_subscriptions[chat_id] = set()

                self._chat_subscriptions[chat_id].add(user_id)
                self._user_subscriptions[user_id].add(chat_id)

        logger.info(f"User {user_id} subscribed to {len(chat_ids)} chats")

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

        logger.debug(f"User {user_id} unsubscribed from chat {chat_id}")

    async def send_to_chat(
        self, chat_id: int, message: dict, exclude_user: int | None = None
    ):
        """
        Отправить сообщение всем участникам чата (CROSS-PROCESS).
        Проходит через pg_notify → все workers.
        """
        await pg_pubsub.publish(
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
        await pg_pubsub.publish(
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
        await pg_pubsub.publish(
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

    async def handle_pg_event(self, event: dict):
        """Обработчик event-ов от pg_pubsub."""
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
            await self.subscribe_to_chat(user_id, chat_id)
            await self._send_to_user(
                user_id, {"type": "chat_created", "chat_id": chat_id}
            )

    async def _send_to_websocket(self, websocket: WebSocket, message: dict):
        """Отправить сообщение в конкретный websocket."""
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")

    async def _send_to_user(self, user_id: int, message: dict):
        """
        Отправить сообщение во все соединения пользователя.

        Args:
            user_id: ID пользователя
            message: Сообщение
        """
        async with self._lock:
            websockets = self._connections.get(user_id, set()).copy()

        dead_websockets = []

        for ws in websockets:
            if ws.client_state == WebSocketState.CONNECTED:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to user {user_id}: {e}")
                    dead_websockets.append(ws)
            else:
                dead_websockets.append(ws)

        # Удаляем мёртвые соединения
        if dead_websockets:
            async with self._lock:
                if user_id in self._connections:
                    for ws in dead_websockets:
                        self._connections[user_id].discard(ws)

    async def _broadcast_presence(self, user_id: int, status: str):
        """
        Разослать уведомление о статусе пользователя.

        Args:
            user_id: ID пользователя
            status: Статус (online/offline)
        """
        message = {
            "type": "presence",
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Получаем все чаты пользователя
        async with self._lock:
            user_chats = self._user_subscriptions.get(user_id, set()).copy()

        # Собираем всех уникальных пользователей из этих чатов
        notified_users: Set[int] = set()
        for chat_id in user_chats:
            async with self._lock:
                chat_users = self._chat_subscriptions.get(chat_id, set())
            notified_users.update(chat_users)

        # Убираем самого пользователя
        notified_users.discard(user_id)

        # Отправляем уведомление
        for notify_user_id in notified_users:
            await self._send_to_user(notify_user_id, message)

    def is_online(self, user_id: int) -> bool:
        """Проверить онлайн ли пользователь."""
        return bool(self._connections.get(user_id))

    def get_online_users(self) -> list[int]:
        """Получить список онлайн пользователей."""
        return [uid for uid, conns in self._connections.items() if conns]

    def get_chat_online_users(self, chat_id: int) -> list[int]:
        """Получить онлайн пользователей в конкретном чате."""
        subscribers = self._chat_subscriptions.get(chat_id, set())
        return [uid for uid in subscribers if self.is_online(uid)]

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
            self._user_activity[user_id] = datetime.now(timezone.utc)
            await self._send_to_websocket(websocket, {"type": "pong"})

        elif message_type == "subscribe":
            # Подписка на чат
            chat_id = data.get("chat_id")
            if chat_id:
                await self.subscribe_to_chat(user_id, chat_id)
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


# Глобальный экземпляр менеджера
chat_manager = ConnectionManager()
