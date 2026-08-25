# Copyright 2025 FARA CRM
# Unit tests for cross-process presence — чистая логика, без БД и без сети.
"""
Присутствие сотрудников.

Два свойства, ради которых всё это существует:

1. Presence — про СОТРУДНИКОВ, а не про чаты: в сети видно всех, независимо
   от того, есть ли общий чат (иначе новый сотрудник, у которого чатов нет,
   невидим для всех и сам никого не видит — и позвонить ему нельзя).
2. Presence переживает несколько воркеров: бэкенд крутится в нескольких
   процессах (uvicorn --workers), у каждого свои _connections, поэтому факт
   входа/выхода едет через шину.

Здесь два ConnectionManager сидят на общей фейковой шине — ровно как два
воркера на одном pg_notify.
"""

import pytest
from starlette.websockets import WebSocketState

from backend.base.crm.chat.websocket.manager import ConnectionManager

CHAT = 7
ALICE = 1
BOB = 2


class FakeWS:
    """Минимальный двойник WebSocket: копит то, что в него отправили."""

    def __init__(self, name: str = "ws"):
        self.name = name
        self.sent: list[dict] = []
        self.client_state = WebSocketState.CONNECTED

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.client_state = WebSocketState.DISCONNECTED


class FakeBus:
    """Одна шина на всех «воркеров» — как pg_notify на все LISTEN."""

    def __init__(self):
        self.managers: list[ConnectionManager] = []

    async def publish(self, event_type: str, data: dict) -> None:
        event = {"type": event_type, **data}
        for manager in self.managers:
            await manager.handle_pubsub_event(event)


def online_seen_by(ws: FakeWS) -> set[int]:
    """Свернуть presence-события так же, как их сворачивает фронт."""
    online: set[int] = set()
    for message in ws.sent:
        if message.get("type") != "presence_update":
            continue
        online.update(message.get("add", []))
        online.difference_update(message.get("remove", []))
    return online


@pytest.fixture
def two_workers():
    """Два менеджера на общей шине."""
    bus = FakeBus()
    workers = (ConnectionManager(), ConnectionManager())
    for manager in workers:
        manager.set_pubsub(bus)
        bus.managers.append(manager)
    return workers


class TestPresence:
    async def test_employees_without_common_chat_see_each_other(
        self, two_workers
    ):
        """
        Главный сценарий: у сотрудников нет ни одного общего чата.

        Раньше присутствие объявлялось из subscribe_all, поэтому новый
        сотрудник (чатов нет — клиент не шлёт subscribe_all вовсе) не
        появлялся в сети ни у кого и сам никого не видел.
        """
        w1, w2 = two_workers
        ws_a, ws_b = FakeWS("alice"), FakeWS("bob")

        await w1.connect(ws_a, ALICE)
        await w2.connect(ws_b, BOB)

        assert online_seen_by(ws_b) == {ALICE}
        assert online_seen_by(ws_a) == {BOB}

    async def test_users_on_different_workers_see_each_other(
        self, two_workers
    ):
        w1, w2 = two_workers
        ws_a, ws_b = FakeWS("alice"), FakeWS("bob")

        await w1.connect(ws_a, ALICE)
        await w1.subscribe_to_chats(ALICE, [CHAT])

        await w2.connect(ws_b, BOB)
        await w2.subscribe_to_chats(BOB, [CHAT])

        assert online_seen_by(ws_b) == {ALICE}
        assert online_seen_by(ws_a) == {BOB}

    async def test_disconnect_reaches_other_worker(self, two_workers):
        w1, w2 = two_workers
        ws_a, ws_b = FakeWS("alice"), FakeWS("bob")

        await w1.connect(ws_a, ALICE)
        await w2.connect(ws_b, BOB)

        await w2.disconnect(ws_b, BOB)

        assert online_seen_by(ws_a) == set()

    async def test_send_failure_still_reports_offline(self, two_workers):
        """
        Сокет, снятый сбоем отправки, всё равно должен погасить presence.

        _send_to_websocket выкидывает мёртвый сокет сам, и disconnect из
        finally приходит уже к пустому бакету — раньше он молча выходил.
        """
        w1, w2 = two_workers
        ws_a, ws_b = FakeWS("alice"), FakeWS("bob")

        await w1.connect(ws_a, ALICE)
        await w2.connect(ws_b, BOB)
        assert online_seen_by(ws_a) == {BOB}

        async def boom(_message):
            raise RuntimeError("socket is gone")

        ws_b.send_json = boom
        await w2._send_to_user(BOB, {"type": "noop"})

        # Ровно то, что делает ws.py в finally.
        await w2.disconnect(ws_b, BOB)

        assert online_seen_by(ws_a) == set()

    async def test_second_device_keeps_user_online(self, two_workers):
        """Уход с одного воркера не гасит юзера, живого на другом."""
        w1, w2 = two_workers
        ws_a = FakeWS("alice")
        ws_desktop, ws_phone = FakeWS("bob-desktop"), FakeWS("bob-phone")

        await w1.connect(ws_a, ALICE)
        await w1.connect(ws_desktop, BOB)
        await w2.connect(ws_phone, BOB)
        assert online_seen_by(ws_a) == {BOB}

        # Отвалился телефон (другой воркер) — десктоп ещё в сети.
        await w2.disconnect(ws_phone, BOB)

        assert online_seen_by(ws_a) == {BOB}


class TestChatSubscriptions:
    async def test_new_chat_does_not_subscribe_offline_user(self, two_workers):
        """
        Фан-аут NEW_CHAT ходит по всем воркерам, но подписывать там, где
        юзера нет, нельзя: свои чаты он пришлёт в subscribe_all при входе,
        а осевшая подписка потом врёт про его состояние.
        """
        w1, w2 = two_workers
        ws_a = FakeWS("alice")

        await w1.connect(ws_a, ALICE)
        await w1.notify_new_chat_bulk([ALICE, BOB], CHAT)

        assert w2._chat_subscriptions.get(CHAT, set()) == set()
        assert w1._chat_subscriptions[CHAT] == {ALICE}


class TestStaleConnectionReaper:
    async def test_silent_socket_is_closed_and_reported_offline(
        self, two_workers
    ):
        """
        Мобильный уходит молча: TCP рвётся без close-кадра, сервер держит
        юзера онлайн вечно. Жнец ловит таких по тишине.
        """
        w1, w2 = two_workers
        ws_a, ws_b = FakeWS("alice"), FakeWS("bob")

        await w1.connect(ws_a, ALICE)
        await w2.connect(ws_b, BOB)
        assert online_seen_by(ws_a) == {BOB}

        # max_idle_seconds=0 → любое соединение считается молчащим.
        reaped = await w2.reap_stale_connections(max_idle_seconds=0)

        assert reaped == 1
        assert ws_b.client_state == WebSocketState.DISCONNECTED
        assert online_seen_by(ws_a) == set()

    async def test_recent_frame_protects_connection(self, two_workers):
        w1, _ = two_workers
        ws_a = FakeWS("alice")
        await w1.connect(ws_a, ALICE)

        # Кадр только что был (connect его и ставит) — жнецу тут нечего брать.
        assert await w1.reap_stale_connections(max_idle_seconds=60) == 0
        assert ws_a.client_state == WebSocketState.CONNECTED
