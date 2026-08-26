"""
Unit-тесты .sudo() — выполнения операций с полным доступом.

Проверяем ровно то, что ломает безопасность или ломает работу:
- права действуют ВНУТРИ вызова (иначе sudo бесполезен);
- прежняя сессия возвращается после вызова, в том числе после исключения
  (иначе полный доступ протёк бы на весь остаток запроса);
- работает и от класса, и от записи.

No database, no network. Pure function tests.
"""

import asyncio

import pytest

from dotorm.access import (
    AccessChecker,
    Sudo,
    SudoAccessor,
    get_access_session,
    set_access_checker,
    set_access_session,
)


class Marker:
    """Опознаваемая «системная» сессия конкретного проекта."""


class CheckerWithOwnSession(AccessChecker):
    """
    Чекер, у которого своя сессия полного доступа.

    Так делает FARA: её _is_full_access сверяет тип через isinstance, и
    маркер из dotorm полным доступом признан бы не был.
    """

    def system_session(self):
        return Marker()


class Model:
    """Двойник модели: методы записывают, какая сессия была на момент вызова."""

    sudo = SudoAccessor()

    def __init__(self, name="record"):
        self.name = name
        self.seen = None

    async def read(self):
        self.seen = get_access_session()
        return self.name

    async def boom(self):
        self.seen = get_access_session()
        raise RuntimeError("операция упала")

    def sync_call(self):
        self.seen = get_access_session()
        return "sync"

    table = "fake_table"

    @classmethod
    async def class_read(cls):
        return get_access_session()


@pytest.fixture(autouse=True)
def own_checker():
    """Свой чекер на время теста, прежняя сессия — «обычный пользователь»."""
    set_access_checker(CheckerWithOwnSession())
    set_access_session("user-session")
    yield
    set_access_session(None)
    set_access_checker(AccessChecker())


class TestSudo:
    async def test_full_access_inside_the_call(self):
        record = Model()

        await record.sudo().read()

        assert isinstance(record.seen, Marker)

    async def test_previous_session_restored_after_call(self):
        record = Model()

        await record.sudo().read()

        assert get_access_session() == "user-session"

    async def test_previous_session_restored_after_exception(self):
        """Упавшая операция не должна оставлять полный доступ включённым."""
        record = Model()

        with pytest.raises(RuntimeError):
            await record.sudo().boom()

        assert isinstance(record.seen, Marker)
        assert get_access_session() == "user-session"

    async def test_works_from_class(self):
        session = await Model.sudo().class_read()

        assert isinstance(session, Marker)
        assert get_access_session() == "user-session"

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
        assert isinstance(record.seen, Marker)

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
            seen_by_neighbour.append(get_access_session())

        async def under_sudo():
            record = Model()
            await record.sudo().read()

        await asyncio.gather(neighbour(), under_sudo())

        assert seen_by_neighbour == ["user-session"]
