# Copyright 2025 FARA CRM
# Unit tests for the WebSocket ConnectionManager — чистая логика, без БД и сети.
"""
Присутствие сотрудников и доставка событий чата.

Свойства, ради которых всё это существует:

1. Presence — про СОТРУДНИКОВ, а не про чаты: в сети видно всех, независимо
   от того, есть ли общий чат (иначе новый сотрудник, у которого чатов нет,
   невидим для всех и сам никого не видит — и позвонить ему нельзя).
2. Presence переживает несколько воркеров: бэкенд крутится в нескольких
   процессах (uvicorn --workers), у каждого свои _connections, поэтому факт
   входа/выхода едет через шину.
3. События чата адресуются УЧАСТНИКАМ (chat_member), а не подписчикам: клиент
   ничего не заявляет, сервер сам знает, кому доставить, а не участник ничего
   не получает и не может ничего разослать.

Здесь два ConnectionManager сидят на общей фейковой шине — ровно как два
воркера на одном pg_notify, а членство задаёт словарь members.
"""

import pytest
from starlette.websockets import WebSocketState

from backend.base.crm.chat.websocket.manager import ConnectionManager

CHAT = 7
ALICE = 1
BOB = 2
CAROL = 3  # не участник CHAT


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


def events_of(ws: FakeWS, event_type: str) -> list[dict]:
    return [m for m in ws.sent if m.get("type") == event_type]


@pytest.fixture
def members() -> dict[int, list[int]]:
    """chat_id -> участники. Двойник ChatMember.active_user_ids."""
    return {CHAT: [ALICE, BOB]}


@pytest.fixture
def two_workers(members):
    """Два менеджера на общей шине с общим справочником участников."""
    bus = FakeBus()

    async def resolve(chat_id: int) -> list[int]:
        return list(members.get(chat_id, []))

    workers = (ConnectionManager(resolve), ConnectionManager(resolve))
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

        Присутствие объявляется на самом соединении, чаты для этого не нужны.
        """
        w1, w2 = two_workers
        ws_a, ws_b = FakeWS("alice"), FakeWS("bob")

        await w1.connect(ws_a, ALICE)
        await w2.connect(ws_b, BOB)

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


class TestChatDelivery:
    """Адресаты события чата — участники из chat_member, на любом воркере."""

    async def test_message_reaches_members_on_both_workers(self, two_workers):
        """
        Никто ничего не подписывал: участник получает событие только потому,
        что он участник, и на том воркере, где держит сокет.
        """
        w1, w2 = two_workers
        ws_a, ws_b = FakeWS("alice"), FakeWS("bob")
        await w1.connect(ws_a, ALICE)
        await w2.connect(ws_b, BOB)

        await w1.send_to_chat(CHAT, {"type": "new_message", "chat_id": CHAT})

        assert len(events_of(ws_a, "new_message")) == 1
        assert len(events_of(ws_b, "new_message")) == 1

    async def test_exclude_user_skips_all_his_sockets(self, two_workers):
        w1, w2 = two_workers
        ws_desktop, ws_phone, ws_b = (
            FakeWS("alice-desktop"),
            FakeWS("alice-phone"),
            FakeWS("bob"),
        )
        await w1.connect(ws_desktop, ALICE)
        await w2.connect(ws_phone, ALICE)
        await w2.connect(ws_b, BOB)

        await w1.send_to_chat(
            CHAT, {"type": "new_message", "chat_id": CHAT}, exclude_user=ALICE
        )

        assert len(events_of(ws_b, "new_message")) == 1
        assert events_of(ws_desktop, "new_message") == []
        assert events_of(ws_phone, "new_message") == []

    async def test_non_member_gets_nothing(self, two_workers):
        """
        Раньше любой авторизованный мог прислать subscribe на чужой chat_id и
        читать его живой трафик. Теперь список адресатов считает сервер.
        """
        w1, w2 = two_workers
        ws_b, ws_c = FakeWS("bob"), FakeWS("carol")
        await w1.connect(ws_b, BOB)
        await w2.connect(ws_c, CAROL)

        await w1.send_to_chat(CHAT, {"type": "new_message", "chat_id": CHAT})

        assert len(events_of(ws_b, "new_message")) == 1
        assert events_of(ws_c, "new_message") == []

    async def test_typing_from_member_reaches_others_not_sender(
        self, two_workers
    ):
        w1, w2 = two_workers
        ws_a, ws_b = FakeWS("alice"), FakeWS("bob")
        await w1.connect(ws_a, ALICE)
        await w2.connect(ws_b, BOB)

        await w1.handle_message(
            ws_a, ALICE, {"type": "typing", "chat_id": CHAT}
        )

        assert events_of(ws_b, "typing") == [
            {"type": "typing", "chat_id": CHAT, "user_id": ALICE}
        ]
        assert events_of(ws_a, "typing") == []

    async def test_typing_from_non_member_is_ignored(self, two_workers):
        """chat_id в кадре называет клиент — не участник ничего не рассылает."""
        w1, w2 = two_workers
        ws_a, ws_c = FakeWS("alice"), FakeWS("carol")
        await w1.connect(ws_a, ALICE)
        await w2.connect(ws_c, CAROL)

        await w2.handle_message(
            ws_c, CAROL, {"type": "typing", "chat_id": CHAT}
        )
        await w2.handle_message(
            ws_c, CAROL, {"type": "read", "chat_id": CHAT, "message_id": 1}
        )

        assert events_of(ws_a, "typing") == []
        assert events_of(ws_a, "messages_read") == []

    async def test_new_chat_event_reaches_only_connected_user(
        self, two_workers
    ):
        """
        NEW_CHAT ходит по всем воркерам; получает его тот, кто подключён,
        остальные — при следующем входе прочитают список чатов сами.
        """
        w1, _ = two_workers
        ws_a = FakeWS("alice")
        await w1.connect(ws_a, ALICE)

        await w1.notify_new_chat_bulk([ALICE, BOB], CHAT)

        assert events_of(ws_a, "chat_created") == [
            {"type": "chat_created", "chat_id": CHAT}
        ]


class TestCallSignaling:
    async def test_sdp_and_ice_reach_the_peer_on_another_worker(
        self, two_workers
    ):
        """
        offer/answer/ice просто пересылаются адресату из to_user_id.

        Раньше сервер вычислял адресата сам — читал call-сообщение из БД на
        КАЖДЫЙ кадр — и при сбое чтения молча его выбрасывал: invite и
        accepted (они из HTTP) ходили, а SDP с ICE пропадали, из-за чего
        звонок навсегда застревал в «Соединение…».
        """
        w1, w2 = two_workers
        ws_a, ws_b = FakeWS("alice"), FakeWS("bob")
        await w1.connect(ws_a, ALICE)
        await w2.connect(ws_b, BOB)
        ws_b.sent.clear()

        for frame in (
            {"type": "call.offer", "call_id": 1, "to_user_id": BOB, "sdp": {}},
            {
                "type": "call.ice",
                "call_id": 1,
                "to_user_id": BOB,
                "candidate": {},
            },
        ):
            await w1.handle_message(ws_a, ALICE, frame)

        types = [m.get("type") for m in ws_b.sent]
        assert types == ["call.offer", "call.ice"]

    async def test_signal_without_addressee_is_not_broadcast(
        self, two_workers
    ):
        """Кадр без to_user_id никому не уходит (а не всем подряд)."""
        w1, w2 = two_workers
        ws_a, ws_b = FakeWS("alice"), FakeWS("bob")
        await w1.connect(ws_a, ALICE)
        await w2.connect(ws_b, BOB)
        ws_b.sent.clear()

        await w1.handle_message(
            ws_a, ALICE, {"type": "call.answer", "call_id": 1, "sdp": {}}
        )

        assert ws_b.sent == []


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
