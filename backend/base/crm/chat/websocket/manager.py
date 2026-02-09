# Copyright 2025 FARA CRM
# Chat module - WebSocket manager for real-time messaging

import asyncio
import logging
from typing import Dict, Set
from datetime import datetime, timezone

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Менеджер WebSocket соединений для чата.

    Управляет:
    - Подключениями пользователей
    - Подписками на чаты
    - Рассылкой сообщений участникам чата
    - Статусами онлайн/оффлайн
    """

    def __init__(self):
        # user_id -> WebSocket connection
        self._connections: Dict[int, WebSocket] = {}

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

        Args:
            websocket: WebSocket соединение (уже accepted)
            user_id: ID пользователя

        Returns:
            True если успешно подключен
        """
        try:
            # websocket.accept() уже вызван в роутере

            async with self._lock:
                # Закрываем предыдущее соединение если есть
                if user_id in self._connections:
                    old_ws = self._connections[user_id]
                    try:
                        await old_ws.close()
                    except Exception:
                        pass

                self._connections[user_id] = websocket
                self._user_activity[user_id] = datetime.now(timezone.utc)

                if user_id not in self._user_subscriptions:
                    self._user_subscriptions[user_id] = set()

            logger.info(f"User {user_id} connected to WebSocket")

            # Отправляем подтверждение подключения
            await self._send_to_user(
                user_id,
                {
                    "type": "connected",
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Уведомляем других о появлении пользователя онлайн
            await self._broadcast_presence(user_id, "online")

            return True

        except Exception as e:
            logger.error(f"Error connecting user {user_id}: {e}")
            return False

    async def disconnect(self, user_id: int):
        """
        Отключить пользователя.

        Args:
            user_id: ID пользователя
        """
        async with self._lock:
            # Удаляем соединение
            if user_id in self._connections:
                del self._connections[user_id]

            # Удаляем из всех подписок на чаты
            if user_id in self._user_subscriptions:
                for chat_id in self._user_subscriptions[user_id]:
                    if chat_id in self._chat_subscriptions:
                        self._chat_subscriptions[chat_id].discard(user_id)
                del self._user_subscriptions[user_id]

            # Удаляем активность
            if user_id in self._user_activity:
                del self._user_activity[user_id]

        logger.info(f"User {user_id} disconnected from WebSocket")

        # Уведомляем других о выходе пользователя
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

            self._chat_subscriptions[chat_id].add(user_id)

            if user_id not in self._user_subscriptions:
                self._user_subscriptions[user_id] = set()

            self._user_subscriptions[user_id].add(chat_id)

        logger.debug(f"User {user_id} subscribed to chat {chat_id}")

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
        Отправить сообщение всем участникам чата.

        Args:
            chat_id: ID чата
            message: Сообщение для отправки
            exclude_user: ID пользователя которому не отправлять (обычно автор)
        """
        async with self._lock:
            subscribers = self._chat_subscriptions.get(chat_id, set()).copy()

        logger.debug(
            f"send_to_chat: chat_id={chat_id}, subscribers={subscribers}, exclude_user={exclude_user}"
        )

        for user_id in subscribers:
            if exclude_user and user_id == exclude_user:
                continue
            await self._send_to_user(user_id, message)

    async def send_to_user(self, user_id: int, message: dict):
        """
        Публичный метод для отправки сообщения пользователю.

        Args:
            user_id: ID пользователя
            message: Сообщение
        """
        await self._send_to_user(user_id, message)

    async def _send_to_user(self, user_id: int, message: dict):
        """
        Отправить сообщение конкретному пользователю.

        Args:
            user_id: ID пользователя
            message: Сообщение
        """
        async with self._lock:
            websocket = self._connections.get(user_id)

        if websocket and websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")
                await self.disconnect(user_id)

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
        return user_id in self._connections

    def get_online_users(self) -> list[int]:
        """Получить список онлайн пользователей."""
        return list(self._connections.keys())

    def get_chat_online_users(self, chat_id: int) -> list[int]:
        """Получить онлайн пользователей в конкретном чате."""
        subscribers = self._chat_subscriptions.get(chat_id, set())
        return [uid for uid in subscribers if self.is_online(uid)]

    async def handle_message(self, user_id: int, data: dict):
        """
        Обработать входящее сообщение от клиента.

        Args:
            user_id: ID пользователя
            data: Данные сообщения
        """
        message_type = data.get("type")

        if message_type == "ping":
            # Heartbeat
            self._user_activity[user_id] = datetime.now(timezone.utc)
            await self._send_to_user(user_id, {"type": "pong"})

        elif message_type == "subscribe":
            # Подписка на чат
            chat_id = data.get("chat_id")
            if chat_id:
                await self.subscribe_to_chat(user_id, chat_id)
                await self._send_to_user(
                    user_id, {"type": "subscribed", "chat_id": chat_id}
                )

        elif message_type == "subscribe_all":
            # Подписка на несколько чатов одним запросом
            chat_ids = data.get("chat_ids", [])
            if chat_ids:
                await self.subscribe_to_chats(user_id, chat_ids)
                await self._send_to_user(
                    user_id,
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
                await self._send_to_user(
                    user_id, {"type": "unsubscribed", "chat_id": chat_id}
                )

        elif message_type == "typing":
            # Индикатор набора текста
            chat_id = data.get("chat_id")
            if chat_id:
                await self.send_to_chat(
                    chat_id,
                    {"type": "typing", "chat_id": chat_id, "user_id": user_id},
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
