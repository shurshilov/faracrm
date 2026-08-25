# Copyright 2025 FARA CRM
# Chat module - WebSocket manager for real-time messaging

import asyncio
from enum import Enum
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Set

from fastapi import WebSocket
from starlette.websockets import WebSocketState

if TYPE_CHECKING:
    from .pubsub.base import PubSubBackend

logger = logging.getLogger(__name__)

# Сколько секунд соединение может молчать, прежде чем считать его мёртвым.
# Клиент шлёт ping раз в 30 секунд, так что это 4 пропущенных пинга.
#
# Зачем вообще: мобильный браузер усыпляет вкладку, а сотовый NAT/переход
# WiFi↔LTE рвут TCP БЕЗ close-кадра. Сокет остаётся "живым" для обеих
# сторон: сервер держит юзера в _connections (все видят его онлайн, хотя
# он ушёл), клиент считает readyState=OPEN и не переподключается.
WS_IDLE_TIMEOUT_SECONDS = 120
WS_REAP_INTERVAL_SECONDS = 60


class WebsocketCommand(str, Enum):
    ping = "ping"
    subscribe = "subscribe"
    subscribe_all = "subscribe_all"
    unsubscribe = "unsubscribe"
    typing = "typing"
    read = "read"

    # ── WebRTC call signaling ──
    # (см. docs/calls-webrtc.md). Клиент → сервер:
    call_invite_ack = (
        "call.invite_ack"  # подтверждение получения invite (presence check)
    )
    call_offer = "call.offer"  # SDP offer
    call_answer = "call.answer"  # SDP answer
    call_ice = "call.ice"  # ICE candidate


class PubSubCommand(str, Enum):
    SEND_CHAT = "send_to_chat"
    SEND_USER = "send_to_user"
    NEW_CHAT = "notify_new_chat"
    # Cross-worker уведомление "callee получил invite с ack'нулся".
    # Будит asyncio.Event в HTTP /calls/start на любом воркере.
    CALL_ACK = "call_ack"

    # Presence. Кто онлайн — знание ЛОКАЛЬНОЕ: _connections у каждого
    # воркера свой. Поэтому "я вошёл"/"я вышел" должны обойти все воркеры,
    # иначе сотрудники, попавшие в разные процессы, не увидят друг друга.
    PRESENCE_HELLO = "presence_hello"
    PRESENCE_BYE = "presence_bye"


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

        # websocket -> время последнего кадра ОТ КЛИЕНТА. Именно посокетно,
        # а не по юзеру: у юзера с двумя устройствами живые пинги одного
        # маскировали бы намертво зависший второй сокет.
        self._ws_activity: dict[WebSocket, datetime] = {}

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
                self._ws_activity[websocket] = now

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

            # Присутствие объявляем сразу по факту соединения — сотрудник
            # должен быть виден в сети независимо от того, есть ли у него
            # чаты (см. секцию PRESENCE). Публикуем на каждое соединение:
            # так и вторая вкладка получает снимок, кто сейчас онлайн.
            await self._presence_publish(PubSubCommand.PRESENCE_HELLO, user_id)

            return True

        except Exception as e:
            logger.error("Error connecting user %s: %s", user_id, e)
            return False

    async def disconnect(self, websocket: WebSocket, user_id: int):
        """
        Отключить конкретное WebSocket соединение пользователя.

        Под локом снимаем сокет и, если живых соединений не осталось, чистим
        подписки. Рассылка presence=offline идёт вне лока и ЧЕРЕЗ ШИНУ
        (PRESENCE_BYE): остальные сотрудники сидят на других воркерах.

        Args:
            websocket: WebSocket соединение для отключения
            user_id: ID пользователя
        """
        gone = False
        remaining = 0

        async with self._lock:
            self._ws_activity.pop(websocket, None)

            conns = self._connections.get(user_id)
            if conns is None:
                # Бакета нет — отключение уже отработало (повторный вызов из
                # ws.py или жнеца), BYE не дублируем.
                return
            conns.discard(websocket)

            if conns:
                remaining = len(conns)
            else:
                del self._connections[user_id]
                for chat_id in self._user_subscriptions.pop(user_id, set()):
                    subs = self._chat_subscriptions.get(chat_id)
                    if subs is not None:
                        subs.discard(user_id)
                gone = True

        logger.info(
            "User %s disconnected from WebSocket (remaining connections: %s)",
            user_id,
            remaining,
        )

        # Если юзер держит сокет ещё где-то (второе устройство), тот воркер
        # переподтвердит присутствие — см. _presence_dispatch.
        if gone:
            await self._presence_publish(PubSubCommand.PRESENCE_BYE, user_id)

    async def subscribe_to_chats(self, user_id: int, chat_ids: list[int]):
        """
        Подписать пользователя на несколько чатов одной операцией.

        Только адресация сообщений: по этим подпискам решается, кому на
        ЭТОМ воркере доставлять события чата. К присутствию отношения не
        имеет — оно объявляется на самом соединении (см. секцию PRESENCE).

        Args:
            user_id: ID пользователя
            chat_ids: Список ID чатов
        """
        if not chat_ids:
            return

        async with self._lock:
            subscriptions = self._user_subscriptions.setdefault(user_id, set())
            for chat_id in chat_ids:
                self._chat_subscriptions.setdefault(chat_id, set()).add(
                    user_id
                )
                subscriptions.add(chat_id)

        logger.info("User %s subscribed to %s chats", user_id, len(chat_ids))

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
                PubSubCommand.SEND_CHAT,
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
                PubSubCommand.SEND_USER,
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
                PubSubCommand.NEW_CHAT,
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                },
            )

    async def notify_new_chat_bulk(
        self, user_ids: list[int], chat_id: int
    ) -> None:
        """Уведомить нескольких пользователей о новом/восстановленном чате
        ПАРАЛЛЕЛЬНО (gather). Одиночный сбой доставки не роняет остальных —
        глушим поштучно (return_exceptions) и логируем. Пустой список — no-op.

        Используется, например, при восстановлении мягко удалённого чата
        (Chat.reactivate): чат надо вернуть в сайдбар сразу всем участникам.
        """
        user_ids = list(user_ids)
        if not user_ids:
            return
        results = await asyncio.gather(
            *(self.notify_new_chat(uid, chat_id) for uid in user_ids),
            return_exceptions=True,
        )
        for uid, res in zip(user_ids, results):
            if isinstance(res, Exception):
                logger.warning(
                    "notify_new_chat_bulk failed (user=%s chat=%s): %s",
                    uid,
                    chat_id,
                    res,
                )

    # ──────────────────────────────────────────────
    # PRESENCE (cross-process)
    # ──────────────────────────────────────────────
    # Присутствие — про СОТРУДНИКОВ, а не про чаты: в сети видно всех, с кем
    # ты можешь связаться (список сотрудников, звонилка), независимо от того,
    # переписывались вы когда-нибудь или нет. Поэтому событию нужен только
    # user_id, и объявляется оно на самом соединении, не дожидаясь
    # subscribe_all (у нового сотрудника чатов может не быть вовсе — раньше
    # он молча оставался невидимым для всех).
    #
    # Кто онлайн — состояние ПРОЦЕССА: _connections живёт в памяти воркера, а
    # воркеров несколько (uvicorn --workers). Поэтому воркер-инициатор только
    # объявляет факт, а отвечает на него КАЖДЫЙ воркер за своих подключённых.

    async def _presence_publish(self, command: str, user_id: int) -> None:
        """Объявить вход/выход юзера всем воркерам (включая свой)."""
        if self._pubsub:
            # Своя же нотификация вернётся сюда через LISTEN — отдельная
            # локальная ветка не нужна и создала бы дубли.
            await self._pubsub.publish(command, {"user_id": user_id})
        else:
            # Шины нет (тесты, одиночный процесс без pubsub) — не терять
            # presence совсем, обработать на месте.
            await self._presence_dispatch(command, user_id)

    async def _presence_dispatch(self, command: str, user_id: int) -> None:
        """
        Обработать объявление присутствия ЗА СВОИХ подключённых.

        peers — все, кто прямо сейчас держит сокет на ЭТОМ воркере.
        """
        is_bye = command == PubSubCommand.PRESENCE_BYE

        async with self._lock:
            subject_here = bool(self._connections.get(user_id))
            peers = {
                uid
                for uid, conns in self._connections.items()
                if uid != user_id and conns
            }

        if is_bye and subject_here:
            # Юзер отключился на другом воркере, но у нас ещё в сети —
            # переподтверждаем присутствие, иначе чужой disconnect погасит
            # его у всех. HELLO публикуется строго ПОСЛЕ этого BYE, порядок
            # доставки в канале сохраняется — «add» придёт вторым.
            await self._presence_publish(PubSubCommand.PRESENCE_HELLO, user_id)
            return

        if not peers:
            return

        timestamp = datetime.now(timezone.utc).isoformat()
        delta = (
            {"add": [], "remove": [user_id]}
            if is_bye
            else {"add": [user_id], "remove": []}
        )
        await asyncio.gather(
            *[
                self._send_to_user(
                    uid,
                    {
                        "type": "presence_update",
                        **delta,
                        "timestamp": timestamp,
                    },
                )
                for uid in peers
            ],
            return_exceptions=True,
        )

        if is_bye:
            return

        # Вошедшему — снимок наших онлайн-пиров. Он может быть и на другом
        # воркере, тогда только через шину.
        send = self._send_to_user if subject_here else self.send_to_user
        await send(
            user_id,
            {
                "type": "presence_update",
                "add": sorted(peers),
                "remove": [],
                "timestamp": timestamp,
            },
        )

    # ──────────────────────────────────────────────
    # STALE CONNECTIONS REAPER
    # ──────────────────────────────────────────────

    async def reap_stale_connections(
        self, max_idle_seconds: int = WS_IDLE_TIMEOUT_SECONDS
    ) -> int:
        """
        Закрыть соединения, от которых давно не было ни одного кадра.

        Мобильные сети рвут TCP без close-кадра (сон вкладки, NAT оператора,
        WiFi↔LTE). Такой сокет не диагностируется ни одной из сторон: сервер
        считает юзера онлайн (и все видят зелёную точку у ушедшего), клиент
        видит readyState=OPEN и не переподключается. Единственный признак —
        тишина: клиент обязан слать ping раз в 30 секунд.

        Returns:
            Сколько соединений закрыто.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=max_idle_seconds
        )
        stale: list[tuple[int, WebSocket]] = []

        async with self._lock:
            for uid, bucket in self._connections.items():
                for ws in bucket:
                    last = self._ws_activity.get(ws)
                    if last is None or last <= cutoff:
                        stale.append((uid, ws))

        for uid, ws in stale:
            logger.info(
                "Reaping stale WebSocket of user %s (silent > %ss)",
                uid,
                max_idle_seconds,
            )
            # Сначала снимаем из структур (тут же уходит presence=offline),
            # затем закрываем сокет: receive-цикл в ws.py разорвётся сам и
            # вызовет disconnect повторно — он идемпотентен.
            await self.disconnect(ws, uid)
            try:
                await ws.close(code=1001, reason="Idle timeout")
            except Exception as exc:
                logger.debug("Stale WS close failed: %s", exc)

        return len(stale)

    # ──────────────────────────────────────────────
    # PG_NOTIFY EVENT HANDLER
    # Вызывается при получении event от PostgreSQL LISTEN.
    # Выполняет ЛОКАЛЬНУЮ доставку в WebSocket connections этого worker-а.
    # ──────────────────────────────────────────────

    async def handle_pubsub_event(self, event: dict):
        """Обработчик event-ов от pubsub."""
        event_type = event.get("type")

        if event_type == PubSubCommand.SEND_CHAT:
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

        elif event_type == PubSubCommand.SEND_USER:
            await self._send_to_user(event["user_id"], event["message"])

        elif event_type == PubSubCommand.NEW_CHAT:
            user_id = event["user_id"]
            chat_id = event["chat_id"]
            # Только за своих. Подписывать юзера, которого на этом воркере
            # нет, незачем — свои чаты он пришлёт в subscribe_all при входе.
            # А осевшая подписка потом ВРЁТ: его вход выглядит «не первым»
            # для этого чата, и присутствие не объявляется вовсе.
            if not self._connections.get(user_id):
                return
            await self.subscribe_to_chats(user_id, [chat_id])
            await self._send_to_user(
                user_id, {"type": "chat_created", "chat_id": chat_id}
            )

        elif event_type in (
            PubSubCommand.PRESENCE_HELLO,
            PubSubCommand.PRESENCE_BYE,
        ):
            await self._presence_dispatch(event_type, event["user_id"])

        elif event_type == PubSubCommand.CALL_ACK:
            # Локально разбудить pending Event, если он есть в этом воркере.
            call_id = event.get("call_id")
            if call_id is not None:
                self._notify_invite_ack_local(int(call_id))

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
        """
        Удалить сдохший на отправке сокет из user-бакетов.

        Опустевший бакет НЕ удаляем: пустой бакет означает «сокеты кончились,
        но presence=offline ещё не объявлен», и объявит его disconnect,
        который придёт следом из ws.py. Если удалить бакет здесь, disconnect
        сочтёт отключение уже отработавшим и BYE не уйдёт никогда — ушедший
        останется «в сети» у всех. Пустое множество ложно, поэтому все
        проверки «онлайн ли юзер» и так дают False.
        """
        async with self._lock:
            self._ws_activity.pop(ws, None)
            for bucket in self._connections.values():
                bucket.discard(ws)

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

        # Любой кадр — признак жизни ЭТОГО сокета (см. reap_stale_connections).
        async with self._lock:
            self._ws_activity[websocket] = datetime.now(timezone.utc)

        if message_type == WebsocketCommand.ping:
            # Heartbeat — отвечаем только в этот websocket
            await self._send_to_websocket(websocket, {"type": "pong"})

        elif message_type == WebsocketCommand.subscribe:
            # Подписка на чат
            chat_id = data.get("chat_id")
            if chat_id:
                await self.subscribe_to_chats(user_id, [chat_id])
                await self._send_to_websocket(
                    websocket, {"type": "subscribed", "chat_id": chat_id}
                )

        elif message_type == WebsocketCommand.subscribe_all:
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

        elif message_type == WebsocketCommand.unsubscribe:
            # Отписка от чата
            chat_id = data.get("chat_id")
            if chat_id:
                await self.unsubscribe_from_chat(user_id, chat_id)
                await self._send_to_websocket(
                    websocket, {"type": "unsubscribed", "chat_id": chat_id}
                )

        elif message_type == WebsocketCommand.typing:
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

        elif message_type == WebsocketCommand.read:
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

        # ── WebRTC call signaling ─────────────────────────────────────
        # Все call-события tuнeлируются между двумя участниками звонка.
        # Сервер здесь — тупой router через PubSub: нашёл "второго"
        # участника по call_id и переслал ему payload. Бизнес-логики ноль.
        elif message_type in (
            WebsocketCommand.call_offer,
            WebsocketCommand.call_answer,
            WebsocketCommand.call_ice,
        ):
            await self._handle_call_signal(user_id, data)

        elif message_type == WebsocketCommand.call_invite_ack:
            # Callee подтвердил получение invite. Шлём cross-process
            # уведомление, чтобы разбудить HTTP /calls/start в любом
            # воркере (где сидит инициатор).
            call_id = data.get("call_id")
            if call_id is not None:
                # 1) разбудить локально (если /calls/start в этом же воркере)
                self._notify_invite_ack_local(int(call_id))
                # 2) разбудить в любом другом воркере через PubSub
                if self._pubsub:
                    await self._pubsub.publish(
                        PubSubCommand.CALL_ACK,
                        {"call_id": int(call_id)},
                    )

    # ──────────────────────────────────────────────
    # WebRTC signaling helpers
    # ──────────────────────────────────────────────

    async def _handle_call_signal(self, from_user_id: int, data: dict) -> None:
        """
        Пересылка call.offer / call.answer / call.ice от from_user_id
        "второму" участнику звонка.

        Второй участник определяется тут же — по call_id читаем ChatMessage,
        берём chat_id и находим второго chat_member (не автора сообщения).
        """
        call_id = data.get("call_id")
        if call_id is None:
            return

        # Поздний импорт — избегаем циклов при старте.
        from backend.base.system.core.enviroment import env

        try:
            call_msg = await env.models.chat_message.get(int(call_id))
        except Exception:
            logger.warning(
                "call signal: message %s not found (from user %s)",
                call_id,
                from_user_id,
            )
            return

        # Находим "другого" участника direct-чата.
        other_user_id = await self._find_other_direct_user(
            (
                call_msg.chat_id.id
                if hasattr(call_msg.chat_id, "id")
                else call_msg.chat_id
            ),
            from_user_id,
        )
        if not other_user_id:
            logger.warning(
                "call signal: no peer found for call %s (from user %s)",
                call_id,
                from_user_id,
            )
            return

        # Пересылаем payload как есть, меняя только направление.
        # Клиент на той стороне узнаёт событие по `type`.
        await self.send_to_user(other_user_id, data)

    async def _find_other_direct_user(
        self, chat_id: int, not_user_id: int
    ) -> int | None:
        """Найти второго юзера в direct-чате (не равного not_user_id)."""
        from backend.base.system.core.enviroment import env

        members = await env.models.chat_member.search(
            filter=[
                ("chat_id", "=", chat_id),
                ("is_active", "=", True),
            ],
            fields=["user_id"],
            limit=2,
        )
        for m in members:
            uid = m.user_id.id if hasattr(m.user_id, "id") else m.user_id
            if uid and uid != not_user_id:
                return uid
        return None

    # ──────────────────────────────────────────────
    # Presence check (ожидание invite_ack)
    # ──────────────────────────────────────────────
    # Используется в HTTP /calls/start для проверки, что callee
    # реально подключён к WebSocket (в т.ч. в другом воркере).
    #
    # Flow:
    #   1. /calls/start публикует `call.invite` через PubSub на callee
    #   2. Тот же handler регистрирует pending event для call_id
    #   3. Клиент callee получает invite, тут же шлёт `call.invite_ack`
    #   4. Тот воркер где сидит callee обрабатывает ack и...
    #      → публикует cross-process событие `call.invite_ack_cross`
    #        (чтобы ЛЮБОЙ воркер мог разбудить pending event)
    #   5. /calls/start просыпается, возвращает успех
    #
    # Чтобы не изобретать ещё один PubSub канал, мы пересылаем invite_ack
    # обратно инициатору через send_to_user (он же ждёт событие).

    def _register_pending_invite(self, call_id: int) -> "asyncio.Event":
        """
        Зарегистрировать ожидание ack для call_id.
        Возвращает Event, который проснётся при получении ack.

        Вызывается из HTTP /calls/start.
        """
        if not hasattr(self, "_pending_invites"):
            self._pending_invites: dict[int, asyncio.Event] = {}
        ev = asyncio.Event()
        self._pending_invites[call_id] = ev
        return ev

    def _notify_invite_ack_local(self, call_id: int) -> None:
        """Разбудить ожидающий /calls/start (если он в этом же воркере)."""
        pending = getattr(self, "_pending_invites", {})
        ev = pending.get(call_id)
        if ev:
            ev.set()

    def _cleanup_pending_invite(self, call_id: int) -> None:
        """Убрать запись из pending после выхода из /calls/start."""
        pending = getattr(self, "_pending_invites", {})
        pending.pop(call_id, None)
