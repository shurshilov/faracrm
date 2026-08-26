# Copyright 2025 FARA CRM
# Unit tests for PostgreSQL LISTEN supervisor — без БД и без сети.
"""
Живучесть подписки на шину.

asyncpg не восстанавливает LISTEN сам: соединение, закрытое рестартом
postgres или сетевым таймаутом, просто перестаёт приносить события. Публикация
при этом продолжает работать (publish берёт из пула новое соединение на каждую
отправку), поэтому воркер выглядит здоровым, а на деле оглох: его клиентов
видят все, а он не видит никого и не получает чужих сообщений.

Ровно это и проверяем — что оглохший воркер сам возвращается в строй.
"""

import asyncio

import pytest

from backend.base.crm.chat.websocket.pubsub import pg_backend
from backend.base.crm.chat.websocket.pubsub.pg_backend import PgPubSubBackend


class FakeConn:
    """Двойник asyncpg-соединения: помнит подписки и умеет «умирать»."""

    def __init__(self):
        self.listeners: list[tuple[str, object]] = []
        self.closed = False

    async def add_listener(self, channel, callback):
        self.listeners.append((channel, callback))

    async def remove_listener(self, channel, callback):
        self.listeners = [
            item for item in self.listeners if item != (channel, callback)
        ]

    def is_closed(self) -> bool:
        return self.closed


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


@pytest.fixture
async def backend(monkeypatch):
    """Бэкенд с мгновенным health-циклом, чтобы тест не ждал 15 секунд."""
    monkeypatch.setattr(pg_backend, "_HEALTH_INTERVAL", 0.01)
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


class TestListenerSupervisor:
    async def test_subscribes_on_start(self, backend):
        await backend.start_listening(lambda event: asyncio.sleep(0))

        assert len(backend._pool.acquired) == 1
        assert (
            backend._pool.acquired[0].listeners[0][0] == pg_backend.PG_CHANNEL
        )
        assert backend.is_healthy()

    async def test_dead_connection_is_not_healthy(self, backend):
        await backend.start_listening(lambda event: asyncio.sleep(0))
        backend._listener_conn.closed = True

        # Главное свойство: объект соединения остался, но здоровым он не
        # считается — иначе оглохший воркер рапортовал бы «всё хорошо».
        assert not backend.is_healthy()

    async def test_supervisor_resubscribes_after_connection_dies(
        self, backend
    ):
        await backend.start_listening(lambda event: asyncio.sleep(0))
        dead = backend._listener_conn
        dead.closed = True

        assert await _wait_for(lambda: len(backend._pool.acquired) > 1)

        assert backend.is_healthy()
        assert backend._listener_conn is not dead
        assert backend._listener_conn.listeners  # LISTEN повешен заново
        assert dead in backend._pool.released  # мёртвое вернули в пул

    async def test_healthy_connection_is_left_alone(self, backend):
        await backend.start_listening(lambda event: asyncio.sleep(0))
        conn = backend._listener_conn

        await asyncio.sleep(0.05)  # несколько тиков супервизора

        assert backend._listener_conn is conn
        assert len(backend._pool.acquired) == 1

    async def test_stop_cancels_supervisor(self, backend):
        await backend.start_listening(lambda event: asyncio.sleep(0))
        supervisor = backend._supervisor

        await backend.stop()

        assert supervisor.cancelled() or supervisor.done()
        assert not backend.is_healthy()
