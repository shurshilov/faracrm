# Copyright 2025 FARA CRM
# Unit tests for the PostgreSQL pub/sub backend — без БД и без сети.
"""
Живучесть подписки на шину и дисциплина публикации.

asyncpg не восстанавливает LISTEN сам: соединение, закрытое рестартом
postgres или сетевым таймаутом, просто перестаёт приносить события. Публикация
при этом продолжает работать (publish берёт из пула новое соединение на каждую
отправку), поэтому воркер выглядит здоровым, а на деле оглох: его клиентов
видят все, а он не видит никого и не получает чужих сообщений.

Полуоткрытый TCP (NAT/фаервол забыл бездействующее соединение) хуже: даже
is_closed() говорит False. Ловится только пробным запросом.

Публикация внутри транзакции идёт через ЕЁ соединение — Postgres доставит
NOTIFY на COMMIT, и клиент не получит событие раньше данных.
"""

import asyncio
import json

import pytest

from backend.base.crm.chat.websocket.pubsub import pg_backend
from backend.base.crm.chat.websocket.pubsub.pg_backend import PgPubSubBackend


class FakeConn:
    """Двойник asyncpg-соединения: помнит подписки и умеет «умирать»."""

    def __init__(self):
        self.listeners: list[tuple[str, object]] = []
        self.closed = False
        # Полуоткрытый TCP: is_closed() False, но ответов больше не будет.
        self.hung = False
        self.terminated = False
        self.executed: list[tuple] = []

    async def add_listener(self, channel, callback):
        self.listeners.append((channel, callback))

    async def remove_listener(self, channel, callback):
        self.listeners = [
            item for item in self.listeners if item != (channel, callback)
        ]

    def is_closed(self) -> bool:
        return self.closed

    def terminate(self) -> None:
        self.terminated = True
        self.closed = True

    async def execute(self, stmt, *args):
        if self.hung:
            await asyncio.Event().wait()  # никогда не ответит
        self.executed.append((stmt, *args))
        return "SELECT 1"


class FakePool:
    """Пул, раздающий новые соединения и считающий возвраты."""

    def __init__(self):
        self.acquired: list[FakeConn] = []
        self.released: list[FakeConn] = []

    async def acquire(self) -> FakeConn:
        conn = FakeConn()
        self.acquired.append(conn)
        return conn

    async def release(self, conn) -> None:
        self.released.append(conn)


class FakeSession:
    """Двойник TransactionSession: только соединение транзакции."""

    def __init__(self, connection: FakeConn):
        self.connection = connection


@pytest.fixture
async def backend(monkeypatch):
    """Бэкенд с мгновенным health-циклом, чтобы тест не ждал 15 секунд."""
    monkeypatch.setattr(pg_backend, "_HEALTH_INTERVAL", 0.01)
    monkeypatch.setattr(pg_backend, "_HEALTH_PROBE_TIMEOUT", 0.02)
    instance = PgPubSubBackend()
    await instance.setup(pool=FakePool())
    yield instance
    await instance.stop()


async def _wait_for(predicate, timeout: float = 1.0) -> bool:
    """Дождаться условия, не завися от точного числа тиков супервизора."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return False


async def _noop(_event: dict) -> None:
    pass


class TestListenerSupervisor:
    async def test_subscribes_on_start(self, backend):
        await backend.start_listening(_noop)

        assert len(backend._pool.acquired) == 1
        assert (
            backend._pool.acquired[0].listeners[0][0] == pg_backend.PG_CHANNEL
        )
        assert backend.is_healthy()

    async def test_dead_connection_is_not_healthy(self, backend):
        await backend.start_listening(_noop)
        backend._listener_conn.closed = True

        # Главное свойство: объект соединения остался, но здоровым он не
        # считается — иначе оглохший воркер рапортовал бы «всё хорошо».
        assert not backend.is_healthy()

    async def test_supervisor_resubscribes_after_connection_dies(
        self, backend
    ):
        await backend.start_listening(_noop)
        dead = backend._listener_conn
        dead.closed = True

        assert await _wait_for(lambda: len(backend._pool.acquired) > 1)

        assert backend.is_healthy()
        assert backend._listener_conn is not dead
        assert backend._listener_conn.listeners  # LISTEN повешен заново
        assert dead in backend._pool.released  # мёртвое вернули в пул

    async def test_half_open_connection_is_replaced(self, backend):
        """
        Соединение «открыто», но не отвечает: is_closed() врёт, и раньше
        такой воркер оставался глухим до рестарта. Пробный SELECT 1 с
        таймаутом это ловит, зависшее соединение рвётся принудительно.
        """
        await backend.start_listening(_noop)
        hung = backend._listener_conn
        hung.hung = True

        assert await _wait_for(lambda: len(backend._pool.acquired) > 1)

        assert hung.terminated
        assert backend._listener_conn is not hung
        assert backend._listener_conn.listeners

    async def test_healthy_connection_is_left_alone(self, backend):
        await backend.start_listening(_noop)
        conn = backend._listener_conn

        await asyncio.sleep(0.05)  # несколько тиков супервизора

        assert backend._listener_conn is conn
        assert len(backend._pool.acquired) == 1
        # Пробы по нему ходили — значит, проверка живая, а не по is_closed().
        assert ("SELECT 1",) in conn.executed

    async def test_stop_cancels_supervisor(self, backend):
        await backend.start_listening(_noop)
        supervisor = backend._supervisor

        await backend.stop()

        assert supervisor.cancelled() or supervisor.done()
        assert not backend.is_healthy()


class TestPublish:
    async def test_inside_transaction_uses_its_connection(
        self, backend, monkeypatch
    ):
        """
        В транзакции NOTIFY уходит её соединением: Postgres доставит его на
        COMMIT вместе с данными (и отменит при ROLLBACK). Пул не трогаем.
        """
        tx_conn = FakeConn()
        monkeypatch.setattr(
            pg_backend, "get_current_session", lambda: FakeSession(tx_conn)
        )

        await backend.publish(
            "send_to_users", {"user_ids": [1], "message": {}}
        )

        assert len(tx_conn.executed) == 1
        _stmt, channel, payload = tx_conn.executed[0]
        assert channel == pg_backend.PG_CHANNEL
        assert json.loads(payload)["type"] == "send_to_users"
        assert backend._pool.acquired == []

    async def test_outside_transaction_uses_pool_connection(
        self, backend, monkeypatch
    ):
        monkeypatch.setattr(pg_backend, "get_current_session", lambda: None)

        await backend.publish(
            "send_to_users", {"user_ids": [1], "message": {}}
        )

        assert len(backend._pool.acquired) == 1
        conn = backend._pool.acquired[0]
        assert conn.executed[0][1] == pg_backend.PG_CHANNEL
        assert backend._pool.released == [conn]  # вернули в пул

    async def test_oversized_payload_is_dropped(self, backend, monkeypatch):
        """Лимит pg_notify ~8 КБ: такое событие не публикуется вовсе, поэтому
        тело сообщения режет serialize_for_ws ДО публикации."""
        monkeypatch.setattr(pg_backend, "get_current_session", lambda: None)

        await backend.publish(
            "send_to_users", {"message": {"body": "x" * 9000}}
        )

        assert backend._pool.acquired == []


class TestDispatch:
    async def test_notification_reaches_callback(self, backend):
        got: list[dict] = []

        async def callback(event: dict) -> None:
            got.append(event)

        await backend.start_listening(callback)
        backend._on_notification(
            None, 0, pg_backend.PG_CHANNEL, '{"type": "x"}'
        )
        await asyncio.gather(*backend._tasks)

        assert got == [{"type": "x"}]

    async def test_callback_error_does_not_break_listener(self, backend):
        """Сбой обработки одного события не мешает следующим, а ссылки на
        завершённые задачи не копятся."""
        calls: list[str] = []

        async def callback(event: dict) -> None:
            calls.append(event["type"])
            raise RuntimeError("boom")

        await backend.start_listening(callback)
        backend._on_notification(
            None, 0, pg_backend.PG_CHANNEL, '{"type": "a"}'
        )
        backend._on_notification(
            None, 0, pg_backend.PG_CHANNEL, '{"type": "b"}'
        )
        await asyncio.gather(*backend._tasks)
        await asyncio.sleep(0)  # done-callback'и задач

        assert calls == ["a", "b"]
        assert backend._tasks == set()
