"""
Unit-тесты .sudo() — выполнения операций с полным доступом.

Проверяем ровно то, что ломает безопасность или ломает работу:
- флаг поднят ВНУТРИ вызова (иначе sudo бесполезен);
- флаг снят после вызова, в том числе после исключения (иначе полный
  доступ протёк бы на весь остаток запроса);
- сессия в контексте не подменяется — как sudo() в Odoo: автор записи
  и владелец по умолчанию остаются вызывающего;
- работает и от класса, и от записи.

No database, no network. Pure function tests.
"""

import asyncio

import pytest

from dotorm.access import (
    Sudo,
    SudoAccessor,
    get_access_session,
    is_sudo,
    set_access_session,
)


class Model:
    """Двойник модели: методы записывают, что видели на момент вызова."""

    sudo = SudoAccessor()

    def __init__(self, name="record"):
        self.name = name
        self.seen_sudo = None
        self.seen_session = None

    async def read(self):
        self.seen_sudo = is_sudo()
        self.seen_session = get_access_session()
        return self.name

    async def boom(self):
        self.seen_sudo = is_sudo()
        raise RuntimeError("операция упала")

    def sync_call(self):
        self.seen_sudo = is_sudo()
        return "sync"

    table = "fake_table"

    @classmethod
    async def class_read(cls):
        return is_sudo()


@pytest.fixture(autouse=True)
def user_session():
    """Прежняя сессия — «обычный пользователь»."""
    set_access_session("user-session")
    yield
    set_access_session(None)


class TestSudo:
    async def test_full_access_inside_the_call(self):
        record = Model()

        await record.sudo().read()

        assert record.seen_sudo is True

    async def test_flag_dropped_after_call(self):
        record = Model()

        await record.sudo().read()

        assert is_sudo() is False

    async def test_flag_dropped_after_exception(self):
        """Упавшая операция не должна оставлять полный доступ включённым."""
        record = Model()

        with pytest.raises(RuntimeError):
            await record.sudo().boom()

        assert record.seen_sudo is True
        assert is_sudo() is False

    async def test_session_stays_the_callers(self):
        """Права поднимаются, сессия прежняя: автор записи под sudo — тот,
        кто вызвал, а не системный пользователь."""
        record = Model()

        await record.sudo().read()

        assert record.seen_session == "user-session"
        assert get_access_session() == "user-session"

    async def test_works_from_class(self):
        assert await Model.sudo().class_read() is True
        assert is_sudo() is False

    async def test_keeps_the_record(self):
        """От записи sudo обязан сохранить именно ЭТУ запись, а не класс."""
        record = Model(name="седьмая")

        assert await record.sudo().read() == "седьмая"

    async def test_sync_method_is_awaitable_too(self):
        """
        Синхронный метод через sudo тоже возвращает awaitable.

        Единообразие важнее удобства: заранее неизвестно, вернёт метод
        корутину или значение, а права обязаны сниматься после выполнения.
        """
        record = Model()

        assert await record.sudo().sync_call() == "sync"
        assert record.seen_sudo is True

    async def test_non_callable_attribute_passes_through(self):
        assert Sudo(Model()).table == "fake_table"

    async def test_concurrent_calls_do_not_leak_between_tasks(self):
        """
        Соседняя задача не должна увидеть чужой полный доступ.

        ContextVar копируется на задачу, но проверить стоит: протечка здесь
        означала бы тихое повышение прав у параллельного запроса.
        """
        seen_by_neighbour = []

        async def neighbour():
            await asyncio.sleep(0.01)
            seen_by_neighbour.append(is_sudo())

        async def under_sudo():
            record = Model()
            await record.sudo().read()

        await asyncio.gather(neighbour(), under_sudo())

        assert seen_by_neighbour == [False]
